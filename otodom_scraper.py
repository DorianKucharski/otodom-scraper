import json
import logging
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


class OtodomScraper:
    def __init__(self):
        self.__scraper = cloudscraper.create_scraper()

    def scrape_search(self, url: str) -> SearchResultDto:
        search_json = self.__scrape(url)
        logger.info("Successfully scraped search page %s", url)
        return SearchResultDto.from_json(search_json)

    def scrape_ad(self, url: str) -> Optional[AdDto]:
        ad_json = self.__scrape(url)
        logger.info("Successfully scraped ad page %s", url)
        return AdDto.from_json(ad_json)

    def __scrape(self, url: str) -> dict:
        try:
            response = self.__scraper.get(url)
            if response.status_code not in [200, 410]:
                raise Exception(f"Error getting page: {response.status_code} - {url}")
            text = response.text
            soup = BeautifulSoup(text, 'html.parser')
            ad_json_text = soup.find(name='script', attrs={'type': 'application/json'})
            return json.loads(ad_json_text.text)
        except Exception as e:
            logger.error(f"Error scraping url: {url} - {e}")
            raise


if __name__ == "__main__":
    _scraper = OtodomScraper()
    _ad_old_url = "https://www.otodom.pl/pl/oferta/rezerwacja-mieszkanie-wysoki-standard-blisko-uczelni-medycznej-ID4znz8"
    _ad_url = "https://www.otodom.pl/pl/oferta/nowe-2-pokoje-parter-0-prowizji-bez-pcc-ID4zjGQ"
    _ad_house_sale_url = "https://www.otodom.pl/pl/oferta/ustronna-naleczowska-kameralna-inwestycja-lublin-ID4zw63"
    _search_url = "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/lubelskie/lublin/lublin/lublin?page=4&limit=36&by=DEFAULT&direction=DESC&priceMax=1000000"
    _ad_scrape = _scraper.scrape_ad(_ad_old_url)
    print(_ad_scrape)
    # _ad_search = _scraper.scrape_search(_search_url)
    # print(_ad_search)
