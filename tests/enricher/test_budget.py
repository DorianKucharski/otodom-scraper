from __future__ import annotations

import unittest
from contextlib import contextmanager

from enricher.budget import DailyBudget


class _FakeResult:
    def __init__(self, value):
        self.__value = value

    def scalar_one(self):
        return self.__value


class _FakeSession:
    def __init__(self, values: list):
        self.__values = list(values)

    def execute(self, statement):
        return _FakeResult(self.__values.pop(0))


class _FakeDatabaseManager:
    def __init__(self, screening: float, evaluation: float):
        self.__values = [screening, evaluation]

    @contextmanager
    def get_session(self):
        yield _FakeSession(self.__values)


class TestDailyBudget(unittest.TestCase):

    def test_spending_sums_both_stages(self):
        budget = DailyBudget(_FakeDatabaseManager(screening=1.25, evaluation=8.5), limit_usd=None)

        spending = budget.spending_today()

        self.assertAlmostEqual(9.75, spending.total_usd)
        self.assertAlmostEqual(1.25, spending.screening_usd)

    def test_no_limit_is_never_exhausted(self):
        budget = DailyBudget(_FakeDatabaseManager(screening=100.0, evaluation=900.0), limit_usd=None)

        self.assertFalse(budget.is_exhausted())
        self.assertIsNone(budget.remaining_usd())

    def test_spending_below_the_limit_leaves_a_remainder(self):
        budget = DailyBudget(_FakeDatabaseManager(screening=1.0, evaluation=2.0), limit_usd=10.0)

        self.assertAlmostEqual(7.0, budget.remaining_usd())
        self.assertFalse(budget.is_exhausted())

    def test_reaching_the_limit_exhausts_the_budget(self):
        budget = DailyBudget(_FakeDatabaseManager(screening=4.0, evaluation=6.0), limit_usd=10.0)

        self.assertTrue(budget.is_exhausted())

    def test_overspending_never_reports_a_negative_remainder(self):
        budget = DailyBudget(_FakeDatabaseManager(screening=20.0, evaluation=30.0), limit_usd=10.0)

        self.assertEqual(0.0, budget.remaining_usd())


if __name__ == "__main__":
    unittest.main()
