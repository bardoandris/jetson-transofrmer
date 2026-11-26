import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "data_procesisng" / "python"))
from explore_benchmark_gaps import classify, metrics, paired_results


class BenchmarkGapAnalysisTests(unittest.TestCase):
    def setUp(self):
        base = {"model": "model", "model_short": "model", "power_mode": "15W",
                "resolution": 512, "dataset": "bottle", "response_s": 1.5,
                "inference_s": 1.0}
        self.rows = pd.DataFrame([
            {**base, "shot_mode": "one-shot", "test_image": "a", "true_category": "defect", "answer_category": "other", "correct": False},
            {**base, "shot_mode": "one-shot", "test_image": "b", "true_category": "good", "answer_category": "good", "correct": True},
            {**base, "shot_mode": "zero-shot", "test_image": "a", "true_category": "defect", "answer_category": "good", "correct": False},
            {**base, "shot_mode": "zero-shot", "test_image": "b", "true_category": "good", "answer_category": "other", "correct": False},
            {**base, "shot_mode": "zero-shot", "test_image": "reference", "true_category": "good", "answer_category": "good", "correct": True},
        ])

    def test_detection_distinguishes_wrong_defect_category_from_missed_defect(self):
        result = metrics(classify(self.rows)).set_index("shot_mode")
        self.assertEqual(result.loc["one-shot", "defect_recall"], 1)
        self.assertEqual(result.loc["zero-shot", "defect_recall"], 0)
        self.assertEqual(result.loc["one-shot", "false_positive_rate"], 0)
        self.assertEqual(result.loc["zero-shot", "false_positive_rate"], 0.5)
        self.assertEqual(result.loc["one-shot", "balanced_accuracy"], 0.5)

    def test_pair_excludes_unmatched_reference_and_counts_discordance(self):
        row = paired_results(self.rows).iloc[0]
        self.assertEqual(row.n, 2)
        self.assertEqual(row.difference_pp, 50)
        self.assertEqual(row.one_only_correct, 1)
        self.assertEqual(row.zero_only_correct, 0)

    def test_duplicate_or_inconsistent_pairs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            paired_results(pd.concat([self.rows, self.rows.iloc[[0]]], ignore_index=True))
        changed = self.rows.copy()
        changed.loc[2, "true_category"] = "other"
        with self.assertRaisesRegex(ValueError, "True categories differ"):
            paired_results(changed)


if __name__ == "__main__":
    unittest.main()
