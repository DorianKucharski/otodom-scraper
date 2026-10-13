import unittest

from sqlalchemy import update
from sqlalchemy.dialects import postgresql

from data.models import AdEvaluation, AdScreening


class EnrichmentTimestampTest(unittest.TestCase):
    def test_rewriting_a_screening_stamps_it_again(self):
        self.assertIn("screened_at=CURRENT_TIMESTAMP", _update_sql(AdScreening))

    def test_rewriting_an_evaluation_stamps_it_again(self):
        self.assertIn("evaluated_at=CURRENT_TIMESTAMP", _update_sql(AdEvaluation))


def _update_sql(model) -> str:
    statement = update(model.__table__).values(status="passed")
    return str(statement.compile(dialect=postgresql.dialect())).replace(" ", "")


if __name__ == "__main__":
    unittest.main()
