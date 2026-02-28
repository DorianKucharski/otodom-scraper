import json
import logging

import cloudscraper
from bs4 import BeautifulSoup

from data.search import SearchAdDto

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdSearcher:
    def __init__(self):
        self.__scraper = cloudscraper.create_scraper()
        self.__base_url = "https://www.otodom.pl/pl/wyniki"

    def search_apartments_for_sale(self):
        url = self.__base_url + "/sprzedaz/mieszkanie"

    def search_apartments_for_rent(self):
        url = self.__base_url + "/wynajem/mieszkanie"

    def get_link(
            self,
            offer_type: str,
            object_type: str,
            voivodeship: str,
            city: str,
            district: str
    ):
        url = self.__base_url + f"/{offer_type}/{object_type}/{voivodeship}/{city}/{district}"

    def test(self) -> list[SearchAdDto]:
        url = "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/wielkopolskie/poznan/poznan/poznan?limit=36&by=DEFAULT&direction=DESC"
        response = self.__scraper.get(url)
        if response.status_code != 200:
            raise Exception(f"Error getting page: {response.status_code} - {url}")
        text = response.text
        soup = BeautifulSoup(text, 'html.parser')
        ad_json_text = soup.find(name='script', attrs={'type': 'application/json'})
        ad_json = json.loads(ad_json_text.text)
        logger.info("Successfully scraped page")
        return SearchAdDto.from_json_list(ad_json)


if __name__ == "__main__":
    _searcher = AdSearcher()
    test = _searcher.test()
    print(test)
