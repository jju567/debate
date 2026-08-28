import unittest
from tools import run_python_code, eval_in_memory

class TestTools(unittest.TestCase):
    def test_eval_in_memory_math(self):
        res = eval_in_memory("12 + 34")
        self.assertTrue(res["success"])
        self.assertEqual(res["output"], "=> 46")

    def test_run_python_code(self):
        res = run_python_code("print('hello debate')")
        self.assertTrue(res["success"])
        self.assertIn("hello debate", res["output"])

if __name__ == "__main__":
    unittest.main()
