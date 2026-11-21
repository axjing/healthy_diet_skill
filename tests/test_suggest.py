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

            # 校验高密度量化遥测字段与单位
            self.assertIn("units", res)
            self.assertEqual(res["units"]["cal"], "kcal")
            self.assertIn("telemetry", res)
            self.assertIn("units", res["telemetry"])
            self.assertEqual(res["telemetry"]["units"]["energy"], "kcal")
            self.assertEqual(res["telemetry"]["energy"]["consumed_cal"], 1100.0)
            self.assertEqual(res["telemetry"]["energy"]["target_cal"], 1767)
            self.assertEqual(res["telemetry"]["energy"]["safety_floor"], 1500)
            self.assertEqual(res["telemetry"]["macros"]["protein_g"]["actual"], 40.0)
            self.assertEqual(res["telemetry"]["macros"]["protein_g"]["gap_g"], 93.0)
            self.assertEqual(res["telemetry"]["quality"]["fiber_g"], 10.0)
            self.assertEqual(res["telemetry"]["quality"]["fiber_gap_g"], 15.0)

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

    def test_pacing_phase_no_false_alarm(self):
        # 模拟早餐刚吃完（仅350 kcal），在 pacing 日内进餐模式下不应触发早熟全天扣分
        mock_breakfast = {
            "date": "2026-11-20",
            "totals": {
                "cal": 350.0,
                "protein": 20.0,
                "carb": 40.0,
                "fat": 10.0,
                "fiber": 4.0,
                "sugar": 5.0,
                "sodium": 300.0,
                "exercise_cal": 0,
                "net_cal": 350.0,
                "status": {
                    "cal_remaining": 1400.0,
                    "cal_over": False,
                    "cal_under": True,
                    "protein_pct": 15,
                    "carb_pct": 20,
                    "fat_pct": 18,
                },
                "meal_count": 1,
            },
            "meals": [{"meal": "早餐"}],
            "exercise": [],
        }
        targets = {
            "cal_target": 1750,
            "safety_floor": 1500,
            "protein_g_target": 130,
            "carb_g_target": 180,
            "fat_g_target": 55,
        }
        with patch("app.analyze_day", return_value=mock_breakfast):
            res = suggest.evaluate_day("2026-11-20", targets=targets, phase="pacing")
            self.assertEqual(res["phase"], "pacing")
            self.assertEqual(res["score"], 100)
            self.assertNotIn("低于生理安全热量底线", res["issues"])
            self.assertNotIn("热量摄入不足", res["issues"])
            self.assertTrue(any("日内进度" in s for s in res["suggestions"]))

    def test_mps_distribution_and_hydration_telemetry(self):
        # 模拟全天高蛋白 (100g)，但分布严重不均（早餐5g、午餐90g、加餐5g），且全天饮水仅800ml
        mock_day = {
            "date": "2026-09-07",
            "weight": 70.0,
            "water_ml": 800,
            "workout_detected": True,
            "totals": {
                "cal": 1800.0,
                "protein": 100.0,
                "carb": 200.0,
                "fat": 50.0,
                "fiber": 22.0,
                "sugar": 20.0,
                "sodium": 1600.0,
                "exercise_cal": 300.0,
                "net_cal": 1500.0,
                "status": {
                    "cal_remaining": 0.0,
                    "protein_pct": 100,
                    "carb_pct": 100,
                    "fat_pct": 100,
                },
                "meal_count": 3,
            },
            "meals": [
                {"meal": "早餐", "totals": {"protein": 5.0, "cal": 200.0}},
                {"meal": "午餐", "totals": {"protein": 90.0, "cal": 1400.0}},
                {"meal": "加餐", "totals": {"protein": 5.0, "cal": 200.0}},
            ],
            "exercise": [{"item": "力量训练", "min": 60, "cal": 300}],
        }
        targets = {
            "weight": 70.0,
            "cal_target": 1800,
            "protein_g_target": 100,
            "carb_g_target": 200,
            "fat_g_target": 50,
            "day_type": "workout",
        }

        with patch("app.analyze_day", return_value=mock_day):
            res = suggest.evaluate_day("2026-09-07", targets=targets, phase="auditing")
            tel = res["telemetry"]
            # 校验 MPS 遥测指标
            self.assertIn("mps", tel)
            self.assertEqual(tel["mps"]["actual_pulses"], 1)  # 仅午餐达到亮氨酸阈值
            self.assertIn("蛋白质摄入过于集中", res["issues"])
            self.assertTrue(any("单餐脉冲" in s for s in res["suggestions"]))

            # 校验水分遥测指标
            self.assertIn("hydration", tel)
            self.assertEqual(tel["hydration"]["consumed_ml"], 800)
            self.assertIn("高蛋白饮食饮水不足", res["issues"])
            self.assertTrue(any("高蛋白补水预警" in s for s in res["suggestions"]))

    def test_peri_workout_meal_checks(self):
        mock_day = {
            "date": "2026-09-08",
            "weight": 70.0,
            "water_ml": 2500,
            "workout_detected": True,
            "totals": {
                "cal": 2000.0,
                "protein": 130.0,
                "carb": 220.0,
                "fat": 55.0,
                "fiber": 25.0,
                "sugar": 15.0,
                "sodium": 1500.0,
                "status": {"protein_pct": 100, "carb_pct": 100, "fat_pct": 100},
            },
            "meals": [
                {"meal": "练前餐", "totals": {"carb": 10.0, "fat": 20.0, "protein": 10.0}},
                {"meal": "练后餐", "totals": {"carb": 40.0, "fat": 5.0, "protein": 12.0}},
            ],
            "exercise": [],
        }
        targets = {
            "weight": 70.0,
            "cal_target": 2000,
            "protein_g_target": 130,
            "carb_g_target": 220,
            "fat_g_target": 55,
        }

        with patch("app.analyze_day", return_value=mock_day):
            res = suggest.evaluate_day("2026-09-08", targets=targets, phase="auditing")
            self.assertIn("练前餐油脂偏高", res["issues"])
            self.assertIn("练后蛋白质不足", res["issues"])
            self.assertTrue(any("练前餐油脂偏高" in s for s in res["suggestions"]))
            self.assertTrue(any("练后合成窗口" in s for s in res["suggestions"]))


if __name__ == "__main__":
    unittest.main()
