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
        self.orig_exports_dir = app.EXPORTS_DIR
        self.orig_history_csv = app.HISTORY_CSV_PATH
        self.orig_custom_foods = app.CUSTOM_FOODS_PATH
        self.orig_settings = app.SETTINGS_PATH

        app.RECORDS_DIR = os.path.join(self.test_dir, "records")
        app.EXPORTS_DIR = os.path.join(self.test_dir, "exports")
        app.HISTORY_CSV_PATH = os.path.join(app.EXPORTS_DIR, "diet_history.csv")
        app.CUSTOM_FOODS_PATH = os.path.join(self.test_dir, "custom_foods.json")
        app.SETTINGS_PATH = os.path.join(self.test_dir, "settings.json")
        os.makedirs(app.RECORDS_DIR, exist_ok=True)
        os.makedirs(app.EXPORTS_DIR, exist_ok=True)

    def tearDown(self):
        app.RECORDS_DIR = self.orig_records_dir
        app.EXPORTS_DIR = self.orig_exports_dir
        app.HISTORY_CSV_PATH = self.orig_history_csv
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
        self.assertIn("units", res)
        self.assertIn("summary", res)
        self.assertIn("units", day)
        self.assertEqual(day["units"]["cal"], "kcal")
        self.assertIn("units", day["meals"][0])
        self.assertIn("summary", day["meals"][0])

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

    def test_weight_logging_and_export_sync(self):
        # 1. 记录饮食并记录体重
        app.add_meal("2026-09-07", "1碗米饭", ts="2026-09-07 12:00:00")
        w_res = app.set_weight("2026-09-07", 72.35)
        self.assertTrue(w_res["ok"])
        self.assertEqual(w_res["weight"], 72.35)

        # 2. 校验 day 与 analyze_day 读取到体重
        analysis = app.analyze_day("2026-09-07")
        self.assertEqual(analysis.get("weight"), 72.35)

        # 3. 校验自动维护的 diet_history.csv 总账文件已存在且写入正确
        self.assertTrue(os.path.exists(app.HISTORY_CSV_PATH))
        with open(app.HISTORY_CSV_PATH, encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("2026-09-07", content)
        self.assertIn("72.35", content)

    def test_python_sdk_and_structured_record(self):
        # 1. SDK profile 初始化
        p_res = app.profile("男", 70.0, 175.0, 30, "轻度", "减重")
        self.assertTrue(p_res["ok"])

        # 2. SDK record 使用结构化条目
        items = [
            {"food": "米饭", "amount": 1, "unit": "碗"},
            {"food": "鸡胸肉", "amount": 150, "unit": "克", "cooking": "煎"}
        ]
        r_res = app.record(items, date="2026-09-08", meal="午餐")
        self.assertTrue(r_res["ok"])
        self.assertEqual(len(r_res["items"]), 2)
        self.assertIn("米饭", r_res["text"])

        # 3. SDK weight 记录
        w_res = app.weight(69.8, date="2026-09-08")
        self.assertTrue(w_res["ok"])
        self.assertEqual(w_res["weight"], 69.8)

        # 4. SDK exercise 记录
        e_res = app.exercise("慢跑", 30, 280, date="2026-09-08")
        self.assertTrue(e_res["ok"])

        # 5. SDK telemetry 遥测验证
        tel = app.telemetry("2026-09-08")
        self.assertEqual(tel["date"], "2026-09-08")
        self.assertIn("telemetry", tel)
        self.assertIn("energy", tel["telemetry"])
        self.assertIn("macros", tel["telemetry"])
        self.assertIn("quality", tel["telemetry"])
        self.assertGreater(tel["telemetry"]["energy"]["consumed_cal"], 400.0)
        self.assertEqual(tel["telemetry"]["energy"]["exercise_cal"], 280.0)

    def test_fitness_peri_workout_and_water(self):
        # 1. 练前餐与练后餐支持 (含英文别名映射)
        r_pre = app.add_meal("2026-09-09", "1根香蕉, 1杯黑咖啡", meal_override="pre_workout")
        self.assertTrue(r_pre["ok"])
        self.assertEqual(r_pre["meal"], "练前餐")

        r_post = app.add_meal("2026-09-09", "1勺蛋白粉, 1盒即食鸡胸肉", meal_override="练后餐")
        self.assertTrue(r_post["ok"])
        self.assertEqual(r_post["meal"], "练后餐")

        # 2. 饮水记录与累加/重设
        w1 = app.add_water("2026-09-09", 500)
        self.assertTrue(w1["ok"])
        self.assertEqual(w1["water_ml"], 500)

        w2 = app.add_water("2026-09-09", 300)
        self.assertEqual(w2["water_ml"], 800)

        w3 = app.water(200, date="2026-09-09")
        self.assertEqual(w3["water_ml"], 1000)

        # 3. 单日分析自动探测运动状态与水分汇总
        analysis = app.analyze_day("2026-09-09")
        self.assertTrue(analysis["workout_detected"])
        self.assertEqual(analysis["water_ml"], 1000)
        self.assertIn("1000 ml", analysis["summary"])

    def test_body_composition_metrics(self):
        # 多维体形成分记录：体重、体脂率、腰围、骨骼肌
        w_res = app.set_weight("2026-09-10", 75.0, body_fat_pct=16.0, waist_cm=82.0, muscle_kg=35.0)
        self.assertTrue(w_res["ok"])
        self.assertEqual(w_res["body_fat_pct"], 16.0)
        self.assertEqual(w_res["waist_cm"], 82.0)
        self.assertEqual(w_res["muscle_kg"], 35.0)
        # 去脂体重 (LBM) = 75 * (1 - 0.16) = 63.0 kg, 脂肪量 = 12.0 kg
        self.assertAlmostEqual(w_res["lbm_kg"], 63.0, places=1)
        self.assertAlmostEqual(w_res["fat_mass_kg"], 12.0, places=1)

        # 验证单日分析回读
        day_res = app.analyze_day("2026-09-10")
        self.assertEqual(day_res["weight"], 75.0)
        self.assertEqual(day_res["body_fat_pct"], 16.0)
        self.assertEqual(day_res["lbm_kg"], 63.0)

        # 验证 CSV 总账包含体脂率、腰围与骨骼肌
        with open(app.HISTORY_CSV_PATH, encoding="utf-8-sig") as f:
            csv_lines = f.readlines()
        header = csv_lines[0]
        self.assertIn("body_fat_pct", header)
        self.assertIn("waist_cm", header)
        self.assertIn("muscle_kg", header)
        last_line = csv_lines[-1]
        self.assertIn("16.0", last_line)
        self.assertIn("82.0", last_line)


if __name__ == "__main__":
    unittest.main()
