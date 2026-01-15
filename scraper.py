import json
from typing import Any, Dict

import cloudscraper
import requests
from bs4 import BeautifulSoup


class Scraper:
    def __init__(self):
        self.__scraper = cloudscraper.create_scraper()

    def scrape(self, url: str) -> Dict[str, Any]:
        response = self.__scraper.get(url)
        if response.status_code != 200:
            raise Exception(f"Error getting page: {response.status_code} - {url}")
        _text = response.text
        _soup = BeautifulSoup(_text, 'html.parser')
        _json = _soup.find(name='script', attrs={'type': 'application/json'})
        return json.loads(_json.text)




# test_url = "https://www.otodom.pl/pl/oferta/rezerwacja-mieszkanie-wysoki-standard-blisko-uczelni-medycznej-ID4znz8"
# scraper = Scraper()
# scrape = scraper.scrape(test_url)
# print(json.dumps(scrape, indent=4))

