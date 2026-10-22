"""DowntimeGuard | Multi-machine educational Streamlit dashboard."""
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from analytics import validate, summarize
from generate_data import generate

st.set_page_config(page_title='DowntimeGuard', page_icon='🏭', layout='wide')
st.markdown('''<style>
.block-container {padding-top:1.4rem; max-width:1450px}
[data-testid="stMetric"] {border:1px solid #dce3e9; border-radius:12px; padding:12px}
</style>''', unsafe_allow_html=True)
st.title('🏭 DowntimeGuard')
st.caption('Smart manufacturing | Multi-machine condition monitoring and downtime analytics')
st.warning('**SYNTHETIC DEMONSTRATION / UNVERIFIED UPLOADED DATA.** This is not measured factory performance, a certified vibration assessment, or a validated fault-prediction system.')

with st.sidebar:
    st.header('Data & configuration')
    source = st.radio('Data source', ['Bundled demonstration', 'Fresh synthetic generation', 'Upload CSV files'])
    st.caption('Uploaded timestamps are never resampled or relabelled.')
    interval = st.number_input('Synthetic sample interval (minutes)', min_value=1, max_value=480, value=5, step=1)
    seed = st.number_input('Synthetic random seed', min_value=0, value=42, step=1)
    shift_minutes = st.number_input('Expected scheduled shift (minutes)', min_value=1, value=480, step=1)
    check_cadence = st.checkbox('Validate uploaded cadence against selected interval', value=False)
    expected_upload_interval = st.number_input('Expected upload interval (minutes)', min_value=1, value=5, step=1, disabled=not check_cadence)
    uploads = st.file_uploader('Upload one combined CSV or several machine CSVs', type='csv', accept_multiple_files=True)
    if st.button('Return to demonstration data', use_container_width=True):
        st.session_state['force_demo'] = True
        st.rerun()
    st.divider()
    st.header('Illustrative thresholds')
    warning = st.number_input('Warning ≥ mm/s', min_value=0.01, value=3.0, step=.1)
    critical = st.number_input('Critical ≥ mm/s', min_value=0.02, value=5.0, step=.1)
    st.header('Illustrative impact assumptions')
    rate = st.number_input('Units per hour per stopped machine', min_value=0.0, value=120.0, step=5.0)
    value = st.number_input('INR per assumed unit', min_value=0.0, value=50.0, step=5.0)

if st.session_state.pop('force_demo', False):
    source = 'Bundled demonstration'

try:
    if source == 'Bundled demonstration':
        raw = pd.read_csv(Path(__file__).parent / 'sample_multi_machine_data.csv')
        description = 'Bundled synthetic CSV · fixed 5-minute samples'
        chosen_upload_interval = None
    elif source == 'Fresh synthetic generation':
        raw = generate(interval=int(interval), shift=int(shift_minutes), seed=int(seed))
        description = f'Fresh synthetic generation · {interval}-minute samples'
        chosen_upload_interval = None
    else:
        if not uploads:
            st.info('Upload one CSV with several machines or several CSV files to continue.')
            st.stop()
        frames = []
        for item in uploads:
            try:
                part = pd.read_csv(item)
            except Exception as exc:
                raise ValueError(f'{item.name}: cannot read CSV ({exc})') from exc
            frames.append(part)
        raw = pd.concat(frames, ignore_index=True)
        description = f'User-uploaded data · {len(uploads)} file(s), not independently verified'
        chosen_upload_interval = int(expected_upload_interval) if check_cadence else None

    clean, detected = validate(raw, expected_interval=chosen_upload_interval, expected_shift=int(shift_minutes))
    processed, summary, events = summarize(clean, detected, warning, critical, rate, value)
except (ValueError, KeyError, TypeError, pd.errors.ParserError) as exc:
    st.error(f'Input validation: {exc}')
    st.info('Check the documented CSV columns, every machine’s timestamp spacing, and the expected shift length. Missing RUNNING vibration readings cannot be inferred.')
    st.stop()

st.caption(f'**Data:** {description} | **Machines:** {len(summary)} | **Detected intervals:** ' + ', '.join(f'{k}: {v:g} min' for k, v in detected.items()))
selection = st.selectbox('View', ['All Machines'] + summary['machine_id'].tolist())
if selection == 'All Machines':
    view = processed
    view_summary = summary
    view_events = events
else:
    view = processed[processed.machine_id == selection]
    view_summary = summary[summary.machine_id == selection]
    view_events = events[events.machine_id == selection]

scheduled = view_summary.scheduled_minutes.sum()
running = view_summary.running_minutes.sum()
down = view_summary.downtime_minutes.sum()
overall = 100*running/scheduled if scheduled else None
attention = view_summary.attention.isin(['Warning', 'Critical']).sum()
metrics = [
    ('Machines', f'{len(view_summary)}'),
    ('Running now', f'{view_summary.latest_operating_state.eq("RUNNING").sum()}'),
    ('Stopped now', f'{view_summary.latest_operating_state.eq("STOPPED").sum()}'),
    ('Availability', f'{overall:.2f}%' if overall is not None else 'N/A'),
    ('Total downtime', f'{down:g} min'),
    ('Attention needed', f'{attention}'),
    ('Stoppage events', f'{len(view_events)}'),
    ('Illustrative value at risk', f'₹{view_summary.illustrative_value_at_risk_inr.sum():,.0f}')
]
for i in range(0, len(metrics), 4):
    cols = st.columns(4)
    for col, (name, display_value) in zip(cols, metrics[i:i+4]):
        col.metric(name, display_value)

st.caption(f'Estimated units not produced: **{view_summary.estimated_units_not_produced.sum():,.1f}**. All production impacts assume {rate:g} units/hour per stopped machine and ₹{value:g}/unit. They are not measured losses.')

st.subheader('Machine comparison')
st.dataframe(view_summary.sort_values('downtime_minutes', ascending=False), use_container_width=True, hide_index=True)
left, right = st.columns(2)
with left:
    st.subheader('Vibration RMS trend')
    fig = px.line(view, x='timestamp', y='vibration_rms_mm_s', color='machine_id', markers=False,
                  labels={'vibration_rms_mm_s':'Vibration RMS (mm/s)', 'timestamp':'Time', 'machine_id':'Machine'})
    fig.add_hline(y=warning, line_dash='dash', line_color='orange', annotation_text='Warning')
    fig.add_hline(y=critical, line_dash='dash', line_color='red', annotation_text='Critical')
    fig.update_layout(height=370, legend_orientation='h')
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader('Downtime ranking (Pareto-style)')
    ranking = view_summary.sort_values('downtime_minutes', ascending=False)
    fig = px.bar(ranking, x='machine_id', y='downtime_minutes', text='downtime_minutes',
                 labels={'machine_id':'Machine', 'downtime_minutes':'Downtime (minutes)'})
    fig.update_layout(height=370)
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader('Operating-state timeline')
    # One interval = one horizontal bar, avoiding visually merging gaps or machines.
    timeline = view.copy()
    timeline['interval_end'] = timeline['timestamp'] + pd.to_timedelta(timeline['interval_minutes'], unit='m')
    fig = px.timeline(timeline, x_start='timestamp', x_end='interval_end', y='machine_id',
                      color='operating_state', color_discrete_map={'RUNNING':'#169b80', 'STOPPED':'#db695d'},
                      labels={'machine_id':'Machine', 'operating_state':'State'})
    fig.update_yaxes(autorange='reversed')
    fig.update_layout(height=370, legend_orientation='h')
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader('Vibration condition distribution')
    counts = view['condition'].value_counts().rename_axis('condition').reset_index(name='readings')
    fig = px.bar(counts, x='condition', y='readings', color='condition',
                 color_discrete_map={'Normal':'#169b80','Warning':'#e3ad4d','Critical':'#d34d49','No reading':'#89939c'},
                 labels={'condition':'Vibration condition','readings':'Sample readings'})
    fig.update_layout(height=370, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.subheader('Downtime events')
if view_events.empty:
    st.info('No stoppage events in the selected machine(s).')
else:
    st.dataframe(view_events, use_container_width=True, hide_index=True)

st.subheader('Rule-based maintenance guidance')
if view_summary.attention.eq('Critical').any():
    st.error('At least one machine has a Critical vibration reading in this shift. An engineer should review the trend, sensor quality and operating context; this is not a diagnosed failure.')
elif view_summary.attention.eq('Warning').any():
    st.warning('Some vibration readings exceed the illustrative Warning threshold. Inspect trends and consider a condition check.')
else:
    st.success('No recorded threshold exceedances. Continue routine monitoring; this does not prove the machines are fault-free.')
st.caption('Operating state and entered stoppage reasons are independent of vibration thresholds. A STOPPED row does not establish why the stop occurred.')

with st.expander('Input validation and source records', expanded=False):
    st.write('Validated data: ', len(processed), 'rows across', len(summary), 'machine(s).')
    st.write('Detected sample cadence by machine (minutes):', detected)
    st.write('Blank vibration readings:', int(processed.vibration_rms_mm_s.isna().sum()), '(allowed only on STOPPED intervals)')
    st.dataframe(view, use_container_width=True, hide_index=True)

st.subheader('Download reports')
def csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8-sig')
buttons = st.columns(4)
buttons[0].download_button('Validated dataset', csv_bytes(processed), 'downtimeguard_validated.csv', 'text/csv', use_container_width=True)
buttons[1].download_button('Machine KPIs', csv_bytes(summary), 'downtimeguard_kpis.csv', 'text/csv', use_container_width=True)
buttons[2].download_button('Stoppage events', csv_bytes(events), 'downtimeguard_events.csv', 'text/csv', use_container_width=True)
buttons[3].download_button('Machine comparison', csv_bytes(summary.sort_values('downtime_minutes', ascending=False)), 'downtimeguard_comparison.csv', 'text/csv', use_container_width=True)

with st.expander('Engineering Concepts — how to explain this project'):
    st.markdown('''
- **Vibration RMS:** a numerical summary of vibration magnitude in mm/s. This demonstration starts with RMS values, not raw accelerometer waveforms.
- **Condition:** Normal (below Warning), Warning (at/above Warning), Critical (at/above Critical), or No reading. Thresholds are illustrative—not universal certified limits.
- **Operating state:** RUNNING or STOPPED from the data. It is independent of vibration condition.
- **Reason:** optional operator-entered stoppage label. It is not inferred from a vibration alert.
- **Event detection:** consecutive STOPPED intervals of the same machine form one downtime event. Gaps or a RUNNING interval end an event.
- **Scheduled-time availability:** RUNNING minutes / Scheduled minutes × 100. This is not OEE, nor proof of mechanical reliability.
- **Pareto-style ranking:** order machines by downtime to identify which warrant investigation first; no causal attribution is implied.
- **Sample resolution:** 5-minute rows represent 5 minutes each. Coarser resolution can miss short stops; uploaded data is validated, never silently reinterpreted.
- **Basic predictive maintenance:** monitoring can support decisions, but failure forecasting needs real longitudinal data, labelled outcomes and independent validation.
- **Potential future IoT:** a compatible sensor, microcontroller, timestamp synchronization and data integrity checks could replace the demonstration CSV.
- **Society 5.0:** human engineers interpret digital measurements and decide actions; no autonomous maintenance decisions are made here.

**Formulas:** Scheduled = number of complete intervals × interval duration; Running = RUNNING intervals × duration; Downtime = STOPPED intervals × duration; Availability = Running / Scheduled × 100; Illustrative units = Downtime / 60 × assumed units per hour; Illustrative value = units × assumed INR per unit.
    ''')
