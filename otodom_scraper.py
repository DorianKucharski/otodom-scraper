import json
import logging
from random import uniform
from time import monotonic, sleep
from typing import Optional

import cloudscraper
from bs4 import BeautifulSoup

from data.ad_dto import AdDto
from data.search_dto import SearchResultDto

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BLOCKED_STATUS_CODES = (403, 429)
GONE_STATUS_CODES = (404, 410)


class OtodomBlockedError(Exception):
    pass


class OtodomScraper:
    def __init__(self, request_delay_seconds: float = 0.0):
        self.__scraper = cloudscraper.create_scraper()
        self.__request_delay_seconds = request_delay_seconds
        self.__last_request_at: Optional[float] = None

    def reset_session(self):
        self.__scraper = cloudscraper.create_scraper()

    def scrape_search(self, url: str) -> SearchResultDto:
        search_json = self.__scrape(url)
        logger.info("Successfully scraped search page %s", url)
        return SearchResultDto.from_json(search_json)

    def scrape_ad(self, url: str) -> Optional[AdDto]:
        ad_json = self.__scrape(url)
        logger.info("Successfully scraped ad page %s", url)
        return AdDto.from_json(ad_json)

    def __wait_for_turn(self):
        if self.__last_request_at is None or self.__request_delay_seconds <= 0:
            return
        delay = self.__request_delay_seconds * uniform(1.0, 1.5)
        remaining = delay - (monotonic() - self.__last_request_at)
        if remaining > 0:
            sleep(remaining)

    def __scrape(self, url: str) -> dict:
        self.__wait_for_turn()
        try:
            self.__last_request_at = monotonic()
            response = self.__scraper.get(url)
            if response.status_code in BLOCKED_STATUS_CODES:
                raise OtodomBlockedError(f"Blocked by otodom: {response.status_code} - {url}")
            if response.status_code != 200 and response.status_code not in GONE_STATUS_CODES:
                raise Exception(f"Error getting page: {response.status_code} - {url}")
            soup = BeautifulSoup(response.text, 'html.parser')
            ad_json_text = soup.find(name='script', attrs={'type': 'application/json'})
            if ad_json_text is None and response.status_code in GONE_STATUS_CODES:
                return {}
            return json.loads(ad_json_text.text)
        except OtodomBlockedError:
            raise
        except Exception as e:
            logger.error(f"Error scraping url: {url} - {e}")
            raise


if __name__ == "__main__":
    _scraper = OtodomScraper()
    _ad_url = "https://www.otodom.pl/pl/oferta/2-pokoje-prestizowe-wykonczone-ID4zXNg"
    _ad_scrape = _scraper.scrape_ad(_ad_url)
    print(_ad_scrape)
