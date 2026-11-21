# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import calc


class TestCalcEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.foods, cls.units, cls.cooking = calc.load_data()
        cls.index = calc.build_index(cls.foods)

    def test_basic_meal_parse(self):
        text = "1碗米饭, 150克鸡胸肉, 1个鸡蛋"
        res = calc.parse_meal(text, self.foods, self.units, self.cooking, self.index)
        self.assertEqual(len(res["items"]), 3)
        self.assertNotIn("unrecognized", res)
        self.assertGreater(res["totals"]["cal"], 300)
        self.assertGreater(res["totals"]["protein"], 30)

    def test_chinese_numbers_and_colloquial_units(self):
        cases = [
            ("二两米饭", 100.0, "米饭"),
            ("半碗白粥", 150.0, "白粥"),
            ("两个鸡蛋", 100.0, "鸡蛋"),
            ("两碗米饭", 300.0, "米饭"),
            ("半斤牛肉", 250.0, "牛肉"),
        ]
        for desc, expected_g, expected_food in cases:
            r = calc.compute_item(desc, self.foods, self.units, self.cooking, self.index)
            self.assertTrue(r["ok"], f"Failed on {desc}: {r.get('error')}")
            self.assertEqual(r["food"], expected_food)
            self.assertAlmostEqual(r["grams"], expected_g, delta=1.0)

    def test_trailing_amount(self):
        r = calc.compute_item("米饭150克", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r["ok"])
        self.assertEqual(r["food"], "米饭")
        self.assertEqual(r["grams"], 150.0)

        r2 = calc.compute_item("鸡蛋2个", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["food"], "鸡蛋")
        self.assertEqual(r2["grams"], 100.0)

    def test_compound_chinese_dishes(self):
        # 西红柿炒鸡蛋 should map to 番茄炒蛋 (not raw tomato)
        r = calc.compute_item("西红柿炒鸡蛋", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r["ok"])
        self.assertEqual(r["food"], "番茄炒蛋")
        self.assertGreater(r["values"]["cal"], 150)

    def test_unrecognized_food_tracking(self):
        text = "1碗米饭, 100克未知火星肉"
        res = calc.parse_meal(text, self.foods, self.units, self.cooking, self.index)
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["food"], "米饭")
        self.assertIn("unrecognized", res)
        self.assertEqual(len(res["unrecognized"]), 1)
        self.assertEqual(res["unrecognized"][0]["input"], "100克未知火星肉")

    def test_negation_exclusion(self):
        text = "不要米饭, 1个鸡蛋"
        res = calc.parse_meal(text, self.foods, self.units, self.cooking, self.index)
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["food"], "鸡蛋")
        self.assertIn("excluded", res)
        self.assertEqual(len(res["excluded"]), 1)
        self.assertEqual(res["excluded"][0]["input"], "不要米饭")

    def test_malformed_numbers_exception_safety(self):
        # 1.2.3 is invalid float, should not crash
        res = calc.parse_meal("1.2.3碗米饭", self.foods, self.units, self.cooking, self.index)
        self.assertEqual(len(res["items"]), 0)
        self.assertIn("unrecognized", res)

    def test_cooking_factor_scaling(self):
        raw = calc.compute_item("150克鸡胸肉", self.foods, self.units, self.cooking, self.index)
        fried = calc.compute_item("150克鸡胸肉(煎)", self.foods, self.units, self.cooking, self.index)
        # Calories should be scaled by factor 1.35
        self.assertAlmostEqual(fried["values"]["cal"], raw["values"]["cal"] * 1.35, delta=2.0)
        # 遵循物理与热力学守恒定律：烹调增加的热量完全来自吸附油脂 (Delta Cal / 9 = Delta Fat)
        delta_cal = fried["values"]["cal"] - raw["values"]["cal"]
        self.assertAlmostEqual(fried["values"]["fat"], raw["values"]["fat"] + delta_cal / 9.0, delta=1.0)
        self.assertIn("cooking_oil_g", fried)
        self.assertAlmostEqual(fried["cooking_oil_g"], delta_cal / 9.0, delta=1.0)
        # Protein and sodium should NOT be scaled by oil cooking factor
        self.assertEqual(fried["values"]["protein"], raw["values"]["protein"])
        self.assertEqual(fried["values"]["sodium"], raw["values"]["sodium"])

    def test_edge_cases_and_robust_parsing(self):
        # 1. 复合口语数量：一碗半米饭 -> 1.5 碗 (225g)
        r1 = calc.compute_item("一碗半米饭", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r1["ok"])
        self.assertEqual(r1["amount"], 1.5)
        self.assertEqual(r1["unit"], "碗")
        self.assertAlmostEqual(r1["grams"], 225.0, delta=1.0)

        # 2. 专用容器单位：两听可乐 -> 2 听 (660g/ml)
        r2 = calc.compute_item("两听可乐", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["amount"], 2.0)
        self.assertEqual(r2["unit"], "听")
        self.assertAlmostEqual(r2["grams"], 660.0, delta=1.0)

        # 3. 模糊前缀剥离：约200克三文鱼 -> 200g
        r3 = calc.compute_item("约200克三文鱼", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r3["ok"])
        self.assertEqual(r3["amount"], 200.0)
        self.assertEqual(r3["unit"], "克")
        self.assertEqual(r3["grams"], 200.0)

        # 4. 特殊分数单位：大半碗米饭 -> 0.75 碗
        r4 = calc.compute_item("大半碗米饭", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r4["ok"])
        self.assertEqual(r4["amount"], 0.75)

        # 5. 生熟态与合理热量：燕麦粥不再放大成900+千卡干燕麦
        r5 = calc.compute_item("一碗燕麦粥", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r5["ok"])
        self.assertEqual(r5["food"], "燕麦粥")
        self.assertLess(r5["values"]["cal"], 200.0)

        # 6. 常见口语通用词与别名命中
        r6 = calc.compute_item("150克鸡肉", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r6["ok"])
        self.assertEqual(r6["food"], "鸡胸肉")

        r7 = calc.compute_item("1杯黑咖啡", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r7["ok"])
        self.assertEqual(r7["food"], "咖啡(黑)")

        r8 = calc.compute_item("500ml水", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(r8["ok"])
        self.assertEqual(r8["values"]["cal"], 0.0)

    def test_structured_items_parsing(self):
        # 1. 结构化字典列表输入 (Agent 推荐协议)
        items_payload = [
            {"food": "米饭", "amount": 1.5, "unit": "碗"},
            {"food": "鸡胸肉", "amount": 150, "unit": "克", "cooking": "煎"}
        ]
        res1 = calc.parse_meal(items_payload, self.foods, self.units, self.cooking, self.index)
        self.assertEqual(len(res1["items"]), 2)
        self.assertEqual(res1["items"][0]["grams"], 225.0)
        self.assertEqual(res1["items"][1]["cooking"], "煎")
        self.assertAlmostEqual(res1["items"][1]["cooking_oil_g"], 7.7, delta=0.5)
        self.assertEqual(res1["totals"]["cal"], 530.0)

        # 2. JSON 字符串结构化输入
        json_payload = '[{"food": "鸡蛋", "amount": 2, "unit": "个", "cooking": "水煮"}]'
        res2 = calc.parse_meal(json_payload, self.foods, self.units, self.cooking, self.index)
        self.assertEqual(len(res2["items"]), 1)
        self.assertEqual(res2["items"][0]["food"], "鸡蛋")
        self.assertEqual(res2["items"][0]["grams"], 100.0)
        self.assertEqual(res2["items"][0]["cooking_factor"], 1.0)

    def test_units_and_summary_metadata(self):
        res = calc.parse_meal("1碗米饭, 100克牛肉冬瓜汤", self.foods, self.units, self.cooking, self.index)
        self.assertTrue(res["items"])
        # 验证每个 item 包含明确单位映射
        for it in res["items"]:
            self.assertIn("units", it)
            self.assertEqual(it["units"]["cal"], "kcal")
            self.assertEqual(it["units"]["protein"], "g")
            self.assertEqual(it["units"]["sodium"], "mg")
        # 验证返回顶层包含 units 与格式化中文 summary
        self.assertIn("units", res)
        self.assertEqual(res["units"]["cal"], "kcal")
        self.assertIn("summary", res)
        self.assertIn("kcal", res["summary"])
        self.assertIn("蛋白质", res["summary"])


if __name__ == "__main__":
    unittest.main()
