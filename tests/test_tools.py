import unittest
from pathlib import Path
from tools import run_python_code, eval_in_memory, write_local_file_content

class TestTools(unittest.TestCase):
    def test_eval_in_memory_math(self):
        res = eval_in_memory("12 + 34")
        self.assertTrue(res["success"])
        self.assertEqual(res["output"], "=> 46")

    def test_run_python_code(self):
        res = run_python_code("print('hello debate')")
        self.assertTrue(res["success"])
        self.assertIn("hello debate", res["output"])

    def test_write_local_file_content(self):
        test_path = Path(__file__).parent / "tmp_test_file.txt"
        try:
            res = write_local_file_content(str(test_path), "test data 123")
            self.assertTrue(res["success"])
            self.assertTrue(test_path.exists())
            self.assertEqual(test_path.read_text(encoding="utf-8"), "test data 123")
        finally:
            test_path.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
