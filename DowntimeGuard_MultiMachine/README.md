# DowntimeGuard — Multi-Machine Monitoring Dashboard

A **synthetic educational prototype**, not real industrial telemetry and not a validated predictive-maintenance product.

## Repository files

```text
DowntimeGuard_MultiMachine/
├── app.py
├── analytics.py
├── generate_data.py
├── sample_multi_machine_data.csv
├── requirements.txt
├── .gitignore
├── README.md
├── PROJECT_STATE.md
└── tests/
    └── test_analytics.py
```

## Run on Windows

1. Install Python 3.11 or newer from https://www.python.org/downloads/ (select **Add Python to PATH**).
2. Download or clone this repository, then open its folder in File Explorer.
3. Click the folder address bar, type `cmd`, press Enter.
4. Run the following commands **one at a time**:

```bat
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python -m streamlit run app.py
```

5. The app normally opens at http://localhost:8501. Keep the Command Prompt window open while using it.

## GitHub upload

1. Visit https://github.com/new, name your repository `DowntimeGuard-MultiMachine`, and create it (public or private as desired).
2. In the repository, choose **Add file → Upload files**.
3. Upload the contents of this folder, keeping `app.py` and `requirements.txt` in the repository root. Upload `tests/test_analytics.py` under a `tests` folder. Hidden `.gitignore` can be included.
4. Click **Commit changes**. No secrets, Python virtual environment, or machine-specific paths should be uploaded.

## Deploy on Streamlit Community Cloud

1. Visit https://share.streamlit.io/ and sign in with GitHub.
2. Choose **Create app → Deploy a public app from GitHub** (menu wording may vary).
3. Select your repository and branch; **main file path:** `app.py`.
4. Deploy, then open the resulting app URL. Dependencies are installed from `requirements.txt`. This app needs no secret keys or paid API.

## Input CSV schema

Required columns: `timestamp,machine_id,operating_state,vibration_rms_mm_s`
Optional: `reason`.

- Timestamp: e.g. `2026-10-21 08:00:00`, beginning of each sample interval.
- Machine ID: any nonblank unique machine identifier.
- Operating state: `RUNNING` or `STOPPED` only; unknown states are rejected, never assumed.
- Vibration: numeric nonnegative RMS vibration value in **mm/s**; blank allowed only for STOPPED intervals.
- Reason: optional entered stoppage explanation. This is NOT inferred from vibration.
- Upload one combined CSV, or multiple non-overlapping machine CSVs. Duplicated machine/time pairs are rejected.
- Each machine must contain uninterrupted, equally spaced observations filling the expected shift (default **480 minutes**). The dashboard compares aligned shift start times.

## Sampling intervals

**Bundled demonstration** has six machines at a fixed 5-minute interval. **Fresh synthetic generation** offers a configurable interval and random seed; the shift duration must be exactly divisible by the interval. **Uploaded data** uses its actual detected timestamp spacing. The separate expected-cadence setting is a validation check, **not** resampling. The app rejects mismatches, irregular gaps and incomplete shifts. Choosing a coarser interval can change how brief simulated stoppages are represented; it must not be used to invent missing data.

## Calculations

Per machine, interval-start timestamps describe one whole consecutive period each.

- Scheduled minutes = valid interval count × detected interval minutes.
- Running minutes = RUNNING count × interval minutes.
- Downtime minutes = STOPPED count × interval minutes.
- Scheduled-time availability (%) = 100 × running / scheduled.
- One event = contiguous STOPPED rows for **the same machine**.
- Overall availability = sum of running minutes / sum of scheduled minutes × 100 (scheduled-time-weighted).
- Illustrative units not produced = downtime minutes / 60 × assumed units/hour per stopped machine.
- Illustrative value at risk = illustrative units × assumed INR/unit.

Vibration state uses **Normal** below Warning, **Warning** at/above Warning and below Critical, and **Critical** at/above Critical; blank stopped readings are **No reading**. Thresholds (default 3.0/5.0 mm/s) are adjustable demonstrations, not universally valid limits. The attention indicator flags any threshold exceedance during the shift. A vibration alert does not prove a machine failure or stoppage cause.

## Use the dashboard

Choose a data source from the sidebar; optionally upload files. Choose **All Machines** or one machine in the main view. Compare KPIs, vibration traces, interval-state timeline, condition counts, downtime ranking and event history. Adjust vibration thresholds and production assumptions. Use the four download buttons for validated rows, KPIs, events and comparison rankings. Use **Return to demonstration data** to switch back to the bundled sample.

## Automated checks

```bat
.venv\Scripts\python -m unittest discover -s tests -v
```

Tests cover six machines, full shift, 1/5/10/15/30-minute intervals, exact threshold boundaries, event aggregation, availability/illustrative values, reproducibility, duplicates, missing RUNNING vibration, time gaps, incomplete shifts and cadence mismatches.

## Troubleshooting

- `py` not recognized: install Python and select PATH during setup, reopen Command Prompt.
- `No module named streamlit`: run `python -m pip install -r requirements.txt` inside your active environment.
- `FileNotFoundError` for CSV: upload the bundled CSV to the same repository folder as `app.py`.
- Duplicate record: remove overlapping CSV rows for the same machine and timestamp.
- Irregular or incomplete timestamps: correct the source data; the app does not fill gaps.
- Interval mismatch: turn off upload cadence checking or enter the actual detected interval, after confirming it matches the source.
- Shift length error: adjust expected scheduled shift only to match the actual interval-covered shift.
- App fails to deploy: inspect **Manage app → Logs** on Streamlit Cloud and verify `app.py`, `analytics.py`, `generate_data.py`, CSV and `requirements.txt` are all at repository root.

## Academic limitations

No sensor, PLC, industrial network, OEE model, fault labels, fault-prediction model, financial validation or production-loss verification is implemented. Downtime reasons are user-supplied or synthetic; the app does not diagnose causes. Engineering judgment is always required. The Apollo Tyres internship was concerned with occupational injury analysis, **not** machine downtime measurements.
