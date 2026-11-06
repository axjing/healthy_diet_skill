# -*- coding: utf-8 -*-
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import suggest


class TestSuggestModule(unittest.TestCase):
    def test_evaluate_day_with_targets(self):
        mock_day_data = {
            "date": "2026-09-07",
            "totals": {
                "cal": 1100.0,
                "protein": 40.0,
                "carb": 120.0,
                "fat": 30.0,
                "fiber": 10.0,
                "sugar": 25.0,
                "sodium": 1200.0,
                "exercise_cal": 200.0,
                "net_cal": 900.0,
                "status": {
                    "cal_remaining": 667.0,
                    "cal_over": False,
                    "cal_under": True,
                    "protein_pct": 30,
                    "carb_pct": 68,
                    "fat_pct": 51,
                },
                "meal_count": 2,
            },
            "meals": [],
            "exercise": [{"item": "跑步", "min": 20, "cal": 200}],
        }
        targets = {
            "cal_target": 1767,
            "safety_floor": 1500,
            "protein_g_target": 133,
            "carb_g_target": 177,
            "fat_g_target": 59,
        }

        with patch("app.analyze_day", return_value=mock_day_data):
            res = suggest.evaluate_day("2026-09-07", targets=targets)
            self.assertEqual(res["date"], "2026-09-07")
            self.assertIn("热量摄入不足", res["issues"])
            self.assertIn("低于生理安全热量底线", res["issues"])
            self.assertIn("蛋白质偏低", res["issues"])
            self.assertIn("膳食纤维不足", res["issues"])
            self.assertLess(res["score"], 80)
            self.assertTrue(any("运动消耗 200 千卡" in s for s in res["suggestions"]))

    def test_evaluate_day_without_targets(self):
        mock_day_data = {
            "date": "2026-09-07",
            "totals": {
                "cal": 1600.0,
                "protein": 80.0,
                "carb": 180.0,
                "fat": 50.0,
                "fiber": 20.0,
                "sugar": 30.0,
                "sodium": 1500.0,
                "exercise_cal": 0,
                "net_cal": 1600.0,
                "meal_count": 3,
            },
            "meals": [],
            "exercise": [],
        }
        with patch("app.analyze_day", return_value=mock_day_data):
            res = suggest.evaluate_day("2026-09-07", targets=None)
            self.assertTrue(any("尚未设置饮食目标档案" in s for s in res["suggestions"]))
            self.assertEqual(res["score"], 100)


if __name__ == "__main__":
    unittest.main()
