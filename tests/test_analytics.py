import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_data import generate
from analytics import validate, summarize

class PipelineTests(unittest.TestCase):
    def test_six_machines_and_full_shift(self):
        d, intervals = validate(generate(), expected_shift=480)
        self.assertEqual(len(intervals), 6)
        self.assertEqual(len(d), 576)
        _, summary, events = summarize(d, intervals)
        self.assertTrue((summary.scheduled_minutes == 480).all())
        self.assertTrue((summary.running_minutes + summary.downtime_minutes == 480).all())
        self.assertEqual(summary.set_index('machine_id').loc['MACHINE-01', 'downtime_minutes'], 45)
        self.assertEqual(summary.set_index('machine_id').loc['MACHINE-05', 'downtime_minutes'], 0)
        self.assertEqual(events.query("machine_id == 'MACHINE-01'").shape[0], 3)
    def test_intervals(self):
        for interval in (1, 5, 10, 15, 30):
            d, detected = validate(generate(interval), expected_shift=480)
            self.assertEqual(len(d), 6*480//interval)
            self.assertTrue(all(v == interval for v in detected.values()))
    def test_threshold_boundaries(self):
        d, cadence = validate(generate())
        d.loc[0, 'vibration_rms_mm_s'] = 3.0
        d.loc[1, 'vibration_rms_mm_s'] = 5.0
        p, _, _ = summarize(d, cadence)
        self.assertEqual(p.iloc[0].condition, 'Warning')
        self.assertEqual(p.iloc[1].condition, 'Critical')
    def test_reject_duplicate(self):
        d = generate()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            validate(__import__('pandas').concat([d, d.iloc[[0]]]))
    def test_reject_missing_running_vibration(self):
        d = generate()
        d.loc[0, 'vibration_rms_mm_s'] = None
        with self.assertRaisesRegex(ValueError, 'RUNNING'):
            validate(d)
    def test_reject_gap(self):
        d = generate()
        d = d.drop(d.index[3])
        with self.assertRaisesRegex(ValueError, 'irregular'):
            validate(d)
    def test_reject_partial_shift(self):
        d = generate()
        d = d[d['timestamp'] != d['timestamp'].min()]
        with self.assertRaises(ValueError):
            validate(d)
    def test_interval_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'detected'):
            validate(generate(), expected_interval=1)
    def test_reproducibility(self):
        self.assertTrue(generate(seed=99).equals(generate(seed=99)))
    def test_value_calculation(self):
        d, cadence = validate(generate())
        _, s, _ = summarize(d, cadence, rate=120, unit_value=50)
        first = s.set_index('machine_id').loc['MACHINE-01']
        self.assertAlmostEqual(first.availability_pct, 90.625)
        self.assertAlmostEqual(first.illustrative_value_at_risk_inr, 4500)

if __name__ == '__main__':
    unittest.main()
