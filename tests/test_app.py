# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import app
import calc


class TestAppModule(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_records_dir = app.RECORDS_DIR
        self.orig_custom_foods = app.CUSTOM_FOODS_PATH
        self.orig_settings = app.SETTINGS_PATH

        app.RECORDS_DIR = os.path.join(self.test_dir, "records")
        app.CUSTOM_FOODS_PATH = os.path.join(self.test_dir, "custom_foods.json")
        app.SETTINGS_PATH = os.path.join(self.test_dir, "settings.json")
        os.makedirs(app.RECORDS_DIR, exist_ok=True)

    def tearDown(self):
        app.RECORDS_DIR = self.orig_records_dir
        app.CUSTOM_FOODS_PATH = self.orig_custom_foods
        app.SETTINGS_PATH = self.orig_settings
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_date_and_time_validation(self):
        self.assertEqual(app.validate_date("2026-09-07"), "2026-09-07")
        self.assertEqual(app.validate_date("2026-9-7"), "2026-09-07")
        with self.assertRaises(ValueError):
            app.validate_date("invalid-date")

        self.assertEqual(app.normalize_ts("2026-09-07 12:30:00"), "2026-09-07 12:30:00")
        self.assertEqual(app.normalize_ts("2026-09-07 12:30"), "2026-09-07 12:30:00")
        with self.assertRaises(ValueError):
            app.normalize_ts("bad-time")

    def test_add_meal_and_unrecognized_warning(self):
        res = app.add_meal("2026-09-07", "1碗米饭, 100克未知火星肉", ts="2026-09-07 12:00:00", meal_override="午餐")
        self.assertTrue(res["ok"])
        self.assertEqual(res["meal"], "午餐")
        self.assertIn("warnings", res)
        self.assertTrue(any("未识别项" in w for w in res["warnings"]))
        self.assertIn("unrecognized", res)

        # Verify persisted record
        day = app.read_day("2026-09-07")
        self.assertEqual(len(day["meals"]), 1)
        self.assertEqual(day["meals"][0]["meal"], "午餐")

    def test_edit_and_delete_meal(self):
        app.add_meal("2026-09-07", "1碗米饭", ts="2026-09-07 12:00:00")
        app.add_meal("2026-09-07", "1个鸡蛋", ts="2026-09-07 18:00:00")

        # Edit meal 0
        edit_res = app.edit_meal("2026-09-07", 0, description="2碗米饭", meal_override="加餐")
        self.assertTrue(edit_res["ok"])
        self.assertEqual(edit_res["meal"]["meal"], "加餐")
        self.assertEqual(edit_res["meal"]["text"], "2碗米饭")

        # Delete meal 1
        del_res = app.delete_meal("2026-09-07", 1)
        self.assertTrue(del_res["ok"])
        self.assertEqual(len(app.read_day("2026-09-07")["meals"]), 1)

    def test_exercise_and_net_calories(self):
        app.add_meal("2026-09-07", "1碗米饭", ts="2026-09-07 12:00:00")
        app.add_exercise("2026-09-07", "慢跑", 30, 250)

        day_analysis = app.analyze_day("2026-09-07")
        self.assertEqual(day_analysis["totals"]["exercise_cal"], 250)
        self.assertAlmostEqual(day_analysis["totals"]["net_cal"], day_analysis["totals"]["cal"] - 250, delta=1.0)

    def test_range_stats_and_meta(self):
        app.add_meal("2026-09-01", "1碗米饭", ts="2026-09-01 12:00:00")
        app.add_exercise("2026-09-02", "慢跑", 30, 300)

        stats = app.range_stats(date(2026, 9, 1), date(2026, 9, 3))
        self.assertEqual(stats["meta"]["days_in_range"], 3)
        self.assertEqual(stats["meta"]["days_with_meals"], 1)
        self.assertEqual(stats["meta"]["days_with_exercise"], 1)
        self.assertEqual(stats["total"]["exercise_cal"], 300.0)

    def test_custom_food_integration(self):
        app.custom_food_add("高蛋白能量棒", cal=350, protein=30, carb=30, fat=10)
        foods, _, custom = app.load_foods()
        self.assertTrue(any(f["name"] == "高蛋白能量棒" for f in custom))

        # Test calculation with custom food
        res = app.add_meal("2026-09-07", "1份高蛋白能量棒", ts="2026-09-07 15:00:00")
        self.assertTrue(res["ok"])
        self.assertNotIn("warnings", res)


if __name__ == "__main__":
    unittest.main()
