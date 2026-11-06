# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import vision


class TestVisionModule(unittest.TestCase):
    def test_clean_vision_output_markdown(self):
        raw = "```\n1碗米饭，150克鸡胸肉(煎)\n```"
        cleaned = vision.clean_vision_output(raw)
        self.assertEqual(cleaned, "1碗米饭，150克鸡胸肉(煎)")

    def test_clean_vision_output_preamble_and_postamble(self):
        raw = "好的，根据图片识别结果：1碗米饭，150克鸡胸肉(煎)。祝您用餐愉快！"
        cleaned = vision.clean_vision_output(raw)
        self.assertEqual(cleaned, "1碗米饭，150克鸡胸肉(煎)")

    def test_clean_vision_output_bullet_list(self):
        raw = "图中食物包含：\n- 1碗米饭\n- 1个鸡蛋\n- 150克鸡胸肉"
        cleaned = vision.clean_vision_output(raw)
        self.assertEqual(cleaned, "1碗米饭，1个鸡蛋，150克鸡胸肉")

    def test_clean_vision_output_bold_markdown(self):
        raw = "**1碗米饭**，**2个鸡蛋**"
        cleaned = vision.clean_vision_output(raw)
        self.assertEqual(cleaned, "1碗米饭，2个鸡蛋")


if __name__ == "__main__":
    unittest.main()
