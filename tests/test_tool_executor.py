import unittest
from tool_executor import execute_tool_call


class TestToolExecutor(unittest.TestCase):
    def test_execute_python_tool(self):
        msg, res = execute_tool_call("execute_python", {"code": "print(2 + 2)"})
        self.assertIn("4", res)
        self.assertIn("4", msg)

    def test_eval_python_expression_tool(self):
        msg, res = execute_tool_call("eval_python_expression", {"code_or_expr": "100 * 5"})
        self.assertIn("500", res)
        self.assertIn("500", msg)

    def test_unknown_tool(self):
        msg, res = execute_tool_call("unknown_function", {})
        self.assertIn("Tuntematon", res)


if __name__ == "__main__":
    unittest.main()
