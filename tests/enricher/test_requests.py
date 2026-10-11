import unittest

from data.models import AdEvaluation, AdScreening, EvaluationRequestStatus, EvaluationStatus, ScreeningStatus
from enricher.requests import request_outcome
from enricher.selector import AdFilter, _filtered_query
from tests.enricher.ad_builder import AdBuilder


class TestRequestOutcome(unittest.TestCase):

    def test_an_evaluated_ad_is_done(self):
        outcome = request_outcome(
            AdBuilder().build(), AdScreening(status=ScreeningStatus.PASSED), AdEvaluation(status=EvaluationStatus.OK)
        )

        self.assertEqual(EvaluationRequestStatus.DONE, outcome.status)

    def test_a_rejected_screening_carries_its_reason(self):
        screening = AdScreening(status=ScreeningStatus.REJECTED, rejection_reason="To cała inwestycja.")

        outcome = request_outcome(AdBuilder().build(), screening, None)

        self.assertEqual((EvaluationRequestStatus.REJECTED, "To cała inwestycja."), (outcome.status, outcome.message))

    def test_an_inactive_ad_fails(self):
        ad = AdBuilder().build()
        ad.status = "removed_by_user"

        self.assertEqual(EvaluationRequestStatus.FAILED, request_outcome(ad, None, None).status)

    def test_a_failed_evaluation_reports_its_error(self):
        evaluation = AdEvaluation(status=EvaluationStatus.FAILED, error_message="timeout")

        outcome = request_outcome(AdBuilder().build(), AdScreening(status=ScreeningStatus.PASSED), evaluation)

        self.assertEqual((EvaluationRequestStatus.FAILED, "timeout"), (outcome.status, outcome.message))


class TestRequestedIdsFilter(unittest.TestCase):

    def test_requested_ids_ignore_the_location_scope(self):
        from sqlalchemy.orm import Session

        query = _filtered_query(Session(), AdFilter(ad_ids=(5, 7), city="Kraków", voivodeship="małopolskie"))
        sql = str(query.statement.compile(compile_kwargs={"literal_binds": True}))

        self.assertIn("ads.id IN (5, 7)", sql)
        self.assertNotIn("cities", sql)


if __name__ == "__main__":
    unittest.main()
