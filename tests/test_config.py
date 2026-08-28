import unittest
from config import load_agents_config, FALLBACK_PARTICIPANTS

class TestConfig(unittest.TestCase):
    def test_load_agents_config(self):
        cfg = load_agents_config()
        self.assertIn("participants", cfg)
        self.assertIn("default_active", cfg)
        self.assertIn("editor_model", cfg)
        self.assertIn("max_history_messages", cfg)
        self.assertIsInstance(cfg["participants"], dict)
        self.assertGreater(len(cfg["participants"]), 0)

    def test_fallback_participants(self):
        self.assertIn("seppo", FALLBACK_PARTICIPANTS)
        self.assertEqual(FALLBACK_PARTICIPANTS["seppo"]["name"], "Seppo")

if __name__ == "__main__":
    unittest.main()
