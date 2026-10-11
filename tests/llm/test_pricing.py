import unittest

from llm.pricing import cost_usd_for


class TestCostUsdFor(unittest.TestCase):

    def test_a_known_model_is_priced(self):
        self.assertAlmostEqual(1.0 + 5.0, cost_usd_for("claude-haiku-4-5", 1_000_000, 1_000_000))

    def test_a_dated_snapshot_is_priced_like_its_alias(self):
        self.assertAlmostEqual(
            cost_usd_for("claude-haiku-4-5", 1000, 200), cost_usd_for("claude-haiku-4-5-20251001", 1000, 200)
        )

    def test_an_unknown_model_has_no_price(self):
        self.assertIsNone(cost_usd_for("gpt-unknown", 1000, 200))


if __name__ == "__main__":
    unittest.main()
