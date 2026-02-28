import json
import logging

import cloudscraper
from bs4 import BeautifulSoup

from data.ad import AdDto

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdScraper:
    def __init__(self):
        self.__scraper = cloudscraper.create_scraper()

    def scrape(self, url: str) -> AdDto:
        response = self.__scraper.get(url)
        if response.status_code != 200:
            raise Exception(f"Error getting page: {response.status_code} - {url}")
        text = response.text
        soup = BeautifulSoup(text, 'html.parser')
        ad_json_text = soup.find(name='script', attrs={'type': 'application/json'})
        ad_json = json.loads(ad_json_text.text)
        logger.info("Successfully scraped page")
        ad_dataclass = AdDto.from_page_json(ad_json)
        logger.info(f"Parsed ad: {ad_dataclass.title}")
        return ad_dataclass


if __name__ == "__main__":
    _scraper = AdScraper()
    _url = "https://www.otodom.pl/pl/oferta/mieszkanie-lublin-45-4m2-2-pietro-2-pok-ID4zYrx"
    _scrape = _scraper.scrape(_url)
    print(_scrape)
