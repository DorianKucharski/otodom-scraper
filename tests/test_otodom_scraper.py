import unittest
from unittest.mock import MagicMock, patch

from otodom_scraper import OtodomBlockedError, OtodomScraper


class OtodomScraperTest(unittest.TestCase):
    def _scraper_returning(self, status_code: int, request_delay_seconds: float = 0.0) -> OtodomScraper:
        session = MagicMock()
        session.get.return_value = MagicMock(status_code=status_code, text="")
        with patch("otodom_scraper.cloudscraper.create_scraper", return_value=session):
            return OtodomScraper(request_delay_seconds)

    def _request_twice(self, scraper: OtodomScraper):
        for _ in range(2):
            with self.assertRaises(OtodomBlockedError):
                scraper.scrape_ad("https://www.otodom.pl/pl/oferta/x")

    @patch("otodom_scraper.uniform", return_value=1.0)
    @patch("otodom_scraper.monotonic", side_effect=[100.0, 100.5, 100.5])
    @patch("otodom_scraper.sleep")
    def test_waits_out_the_rest_of_the_delay_before_the_next_request(self, sleep, _monotonic, _uniform):
        self._request_twice(self._scraper_returning(403, request_delay_seconds=2.0))
        sleep.assert_called_once_with(1.5)

    @patch("otodom_scraper.sleep")
    def test_no_delay_by_default(self, sleep):
        self._request_twice(self._scraper_returning(403))
        sleep.assert_not_called()

    def test_forbidden_is_a_block(self):
        with self.assertRaises(OtodomBlockedError):
            self._scraper_returning(403).scrape_ad("https://www.otodom.pl/pl/oferta/x")

    def test_too_many_requests_is_a_block(self):
        with self.assertRaises(OtodomBlockedError):
            self._scraper_returning(429).scrape_search("https://www.otodom.pl/pl/wyniki")

    def test_server_error_is_not_a_block(self):
        with self.assertRaises(Exception) as context:
            self._scraper_returning(500).scrape_ad("https://www.otodom.pl/pl/oferta/x")
        self.assertNotIsInstance(context.exception, OtodomBlockedError)


if __name__ == "__main__":
    unittest.main()
