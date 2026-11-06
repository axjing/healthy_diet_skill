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
        # Calories and fat should be scaled by factor 1.35
        self.assertAlmostEqual(fried["values"]["cal"], raw["values"]["cal"] * 1.35, delta=2.0)
        self.assertAlmostEqual(fried["values"]["fat"], raw["values"]["fat"] * 1.35, delta=1.0)
        # Protein and sodium should NOT be scaled by oil cooking factor
        self.assertEqual(fried["values"]["protein"], raw["values"]["protein"])
        self.assertEqual(fried["values"]["sodium"], raw["values"]["sodium"])


if __name__ == "__main__":
    unittest.main()
