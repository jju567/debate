import unittest
from model_router import resolve_model, get_fallback_model, ROLE_FALLBACK_MODELS

class TestModelRouter(unittest.TestCase):
    def test_role_fallback_models(self):
        # Tarkistetaan että jokaiselle agentille löytyy täsmällinen ilmainen backup-malli
        self.assertEqual(get_fallback_model("kolli"), "cohere/north-mini-code:free")
        self.assertEqual(get_fallback_model("matti"), "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free")
        self.assertEqual(get_fallback_model("aki"), "nvidia/nemotron-3-super-120b-a12b:free")
        self.assertEqual(get_fallback_model("seppo"), "minimax/minimax-m3:free")
        self.assertEqual(get_fallback_model("legal"), "nvidia/nemotron-3-super-120b-a12b:free")
        self.assertEqual(get_fallback_model("editor"), "openrouter/free")

    def test_explicit_model_preserved(self):
        explicit = "openai/gpt-4o"
        res = resolve_model(explicit, "seppo")
        self.assertEqual(res, explicit)

if __name__ == "__main__":
    unittest.main()
