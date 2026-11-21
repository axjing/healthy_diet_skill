# -*- coding: utf-8 -*-
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import goals


class TestGoalsModule(unittest.TestCase):
    def test_mifflin_bmr(self):
        # Male 70kg, 175cm, 30yo: 10*70 + 6.25*175 - 5*30 + 5 = 700 + 1093.75 - 150 + 5 = 1648.75
        bmr_m = goals.bmr_mifflin("男", 70, 175, 30)
        self.assertAlmostEqual(bmr_m, 1648.75, places=2)

        # Female 50kg, 160cm, 25yo: 10*50 + 6.25*160 - 5*25 - 161 = 500 + 1000 - 125 - 161 = 1214.0
        bmr_f = goals.bmr_mifflin("女", 50, 160, 25)
        self.assertAlmostEqual(bmr_f, 1214.0, places=2)

    def test_sex_differentiated_safety_floor(self):
        # Male safety floor = 1500 kcal
        # Even with extreme cut, male cal_target should not drop below 1500
        res_m = goals.daily_targets("男", 55, 160, 40, activity="久坐", goal="减重")
        self.assertGreaterEqual(res_m["cal_target"], 1500)
        self.assertEqual(res_m["safety_floor"], 1500)

        # Female safety floor = 1200 kcal
        res_f = goals.daily_targets("女", 45, 150, 40, activity="久坐", goal="减重")
        self.assertGreaterEqual(res_f["cal_target"], 1200)
        self.assertEqual(res_f["safety_floor"], 1200)

    def test_protein_per_kg_metric(self):
        res = goals.daily_targets("男", 70, 175, 30, activity="轻度", goal="减重")
        self.assertIn("protein_g_per_kg", res)
        # 133g / 70kg = 1.90 g/kg (reasonable for hypocaloric retention)
        self.assertAlmostEqual(res["protein_g_per_kg"], 1.89, delta=0.1)

    def test_activity_aliases(self):
        res1 = goals.daily_targets("男", 70, 175, 30, activity="久坐", goal="维持")
        res2 = goals.daily_targets("男", 70, 175, 30, activity="不运动", goal="维持")
        self.assertEqual(res1["tdee"], res2["tdee"])

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            goals.daily_targets("男", 10, 175, 30)  # Weight < 20
        with self.assertRaises(ValueError):
            goals.daily_targets("未知", 70, 175, 30)  # Invalid sex
        with self.assertRaises(ValueError):
            goals.daily_targets("男", 70, 175, 30, goal="未知目标")

    def test_adaptive_tdee_calibration(self):
        import tempfile
        import shutil
        test_dir = tempfile.mkdtemp()
        try:
            # 模拟 14 天记录：体重从 80.0kg 降至 79.0kg (-1.0kg)，日均摄入 2000 kcal
            # 物理闭环推导：14天减重1kg说明每日存在 7700/14 = 550 kcal 缺口，真实 TDEE = 2000 - (-550) = 2550 kcal
            from datetime import datetime, timedelta
            base_date = datetime.now() - timedelta(days=15)
            for i in range(15):
                d_str = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                record = {
                    "date": d_str,
                    "meals": [{"totals": {"cal": 2000.0}}],
                    "exercise": [],
                }
                if i == 0:
                    record["weight"] = 80.0
                elif i == 14:
                    record["weight"] = 79.0
                with open(os.path.join(test_dir, f"{d_str}.json"), "w", encoding="utf-8") as f:
                    json.dump(record, f)

            res = goals.calibrate_adaptive_tdee(test_dir, fallback_tdee=2200.0, window_days=30)
            self.assertEqual(res["status"], "calibrated")
            self.assertEqual(res["adaptive_tdee"], 2550)
            self.assertEqual(res["delta_weight_kg"], -1.0)
            self.assertEqual(res["days_span"], 14)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
