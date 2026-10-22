"""DowntimeGuard multi-machine validation and deterministic calculations."""
import numpy as np
import pandas as pd

REQUIRED = ('timestamp', 'machine_id', 'operating_state', 'vibration_rms_mm_s')


def validate(data, expected_interval=None, expected_shift=480):
    """Reject ambiguous data rather than fabricate machine operating records."""
    if data.empty:
        raise ValueError('CSV is empty.')
    missing = [c for c in REQUIRED if c not in data]
    if missing:
        raise ValueError('Missing required columns: ' + ', '.join(missing))
    d = data.copy()
    if 'reason' not in d:
        d['reason'] = ''
    d['reason'] = d['reason'].fillna('').astype(str)
    d['timestamp'] = pd.to_datetime(d['timestamp'], errors='coerce')
    if d['timestamp'].isna().any():
        raise ValueError('Invalid or missing timestamp found.')
    if d['machine_id'].isna().any() or d['machine_id'].astype(str).str.strip().eq('').any():
        raise ValueError('Missing machine_id found.')
    d['machine_id'] = d['machine_id'].astype(str).str.strip()
    d['operating_state'] = d['operating_state'].astype('string').str.upper().str.strip()
    if not d['operating_state'].isin(['RUNNING', 'STOPPED']).all():
        raise ValueError('Unknown/missing operating_state. Use RUNNING or STOPPED; unknown periods cannot count toward availability.')
    raw = d['vibration_rms_mm_s'].astype('string').str.strip()
    nonblank = raw.notna() & ~raw.isin(['', 'nan', 'NaN', 'None'])
    nums = pd.to_numeric(raw, errors='coerce')
    if (nonblank & nums.isna()).any():
        raise ValueError('Non-numeric vibration reading found.')
    if nums.dropna().lt(0).any() or np.isinf(nums.dropna()).any():
        raise ValueError('Vibration must be finite and nonnegative.')
    d['vibration_rms_mm_s'] = nums.astype(float)
    if d.loc[d['operating_state'].eq('RUNNING'), 'vibration_rms_mm_s'].isna().any():
        raise ValueError('Missing vibration on a RUNNING interval. STOPPED intervals may have blank readings.')
    if d.duplicated(['machine_id', 'timestamp']).any():
        raise ValueError('Duplicate machine_id/timestamp records detected (possibly overlapping CSV files).')
    d = d.sort_values(['machine_id', 'timestamp']).reset_index(drop=True)
    intervals = {}
    start_times = {}
    for machine, group in d.groupby('machine_id', sort=True):
        if len(group) < 2:
            raise ValueError(f'{machine}: need at least two readings to detect interval from timestamps.')
        diffs = group['timestamp'].diff().dropna().dt.total_seconds() / 60
        if (diffs <= 0).any() or diffs.nunique() != 1:
            raise ValueError(f'{machine}: irregular timestamps or gaps. Upload contiguous, equally spaced intervals.')
        cadence = float(diffs.iloc[0])
        if cadence <= 0 or not np.isfinite(cadence):
            raise ValueError(f'{machine}: invalid detected interval.')
        if expected_interval is not None and not np.isclose(cadence, expected_interval):
            raise ValueError(f'{machine}: detected {cadence:g} min but selected {expected_interval:g} min. Existing timestamps are not resampled.')
        duration = len(group) * cadence
        if expected_shift is not None and not np.isclose(duration, expected_shift):
            raise ValueError(f'{machine}: incomplete shift ({duration:g} of {expected_shift:g} scheduled minutes).')
        intervals[machine] = cadence
        start_times[machine] = group['timestamp'].iloc[0]
    if len(set(start_times.values())) > 1:
        raise ValueError('Machine shift start times differ; use aligned shifts for this comparison dashboard.')
    return d, intervals


def summarize(d, intervals, warning=3.0, critical=5.0, rate=120, unit_value=50):
    if not (0 < warning < critical):
        raise ValueError('Thresholds must satisfy 0 < Warning < Critical.')
    if rate < 0 or unit_value < 0:
        raise ValueError('Assumed rate and unit value must be nonnegative.')
    d = d.copy()
    d['condition'] = np.select([
        d['vibration_rms_mm_s'].ge(critical),
        d['vibration_rms_mm_s'].ge(warning),
        d['vibration_rms_mm_s'].lt(warning),
    ], ['Critical', 'Warning', 'Normal'], default='No reading')
    d['interval_minutes'] = d['machine_id'].map(intervals)
    rows, events = [], []
    for machine, g in d.groupby('machine_id', sort=True):
        g = g.sort_values('timestamp')
        interval = intervals[machine]
        stopped = g['operating_state'].eq('STOPPED')
        scheduled = len(g) * interval
        downtime = int(stopped.sum()) * interval
        running = scheduled - downtime
        # Contiguous stopped rows per machine are one event.
        starts = stopped & ~stopped.shift(fill_value=False)
        keys = starts.cumsum()
        n_events = 0
        for _, block in g.loc[stopped].groupby(keys[stopped]):
            n_events += 1
            reasons = [x for x in block['reason'].unique() if x.strip()]
            events.append(dict(machine_id=machine, start=block['timestamp'].iloc[0],
                               end=block['timestamp'].iloc[-1] + pd.Timedelta(minutes=interval),
                               duration_minutes=len(block)*interval,
                               reason='; '.join(reasons) if reasons else 'Not recorded'))
        latest = g.iloc[-1]
        conditions = g['condition']
        overall_condition = ('Critical' if conditions.eq('Critical').any() else
                             'Warning' if conditions.eq('Warning').any() else 'Normal')
        rows.append(dict(machine_id=machine, scheduled_minutes=scheduled,
                         running_minutes=running, downtime_minutes=downtime,
                         availability_pct=100*running/scheduled if scheduled else np.nan,
                         stoppage_events=n_events, latest_operating_state=latest['operating_state'],
                         latest_vibration_mm_s=latest['vibration_rms_mm_s'],
                         latest_condition=latest['condition'], attention=overall_condition,
                         estimated_units_not_produced=downtime/60*rate,
                         illustrative_value_at_risk_inr=downtime/60*rate*unit_value,
                         detected_interval_minutes=interval))
    return d, pd.DataFrame(rows), pd.DataFrame(events, columns=['machine_id','start','end','duration_minutes','reason'])
