"""Generate reproducible, explicitly synthetic aligned machine shifts."""
import numpy as np
import pandas as pd

START = pd.Timestamp('2026-10-21 08:00:00')
STOPPAGES = {
 'MACHINE-01': [(70, 85, 'Setup / adjustment'), (210, 220, 'Inspection'), (360, 380, 'Material changeover')],
 'MACHINE-02': [(30, 60, 'Planned changeover'), (250, 270, 'Material shortage')],
 'MACHINE-03': [(95, 105, 'Inspection')],
 'MACHINE-04': [(140, 180, 'Material shortage'), (310, 335, 'Adjustment')],
 'MACHINE-05': [],
 'MACHINE-06': [(15, 35, 'Planned changeover'), (155, 170, 'Inspection'), (385, 415, 'Material shortage')],
}

def generate(interval=5, shift=480, seed=42):
    if not isinstance(interval, int) or interval <= 0 or shift % interval:
        raise ValueError('Sample interval must be a positive whole number dividing shift duration exactly.')
    rng = np.random.default_rng(seed)
    rows = []
    for idx, (machine, blocks) in enumerate(STOPPAGES.items()):
        for minute in range(0, shift, interval):
            reasons = [reason for begin, end, reason in blocks if begin <= minute < end]
            stopped = bool(reasons)
            value = max(0.05, rng.normal(1.7 + idx*.16, .28))
            if idx in (0, 2, 4) and 110 <= minute < 140:
                value += 1.75
            if idx in (1, 3, 5) and 300 <= minute < 325:
                value += 3.6
            rows.append([START + pd.Timedelta(minutes=minute), machine,
                         'STOPPED' if stopped else 'RUNNING',
                         '' if stopped else round(value, 3),
                         reasons[0] if reasons else ''])
    return pd.DataFrame(rows, columns=['timestamp','machine_id','operating_state','vibration_rms_mm_s','reason'])

if __name__ == '__main__':
    generate().to_csv('sample_multi_machine_data.csv', index=False)
