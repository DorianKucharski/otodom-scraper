from __future__ import annotations

import unittest
from datetime import datetime

from data.rcn import parse_flat_sales, tiles

_DOCUMENT = """<?xml version='1.0' encoding="UTF-8" ?>
<wfs:FeatureCollection xmlns:ms="http://mapserver.gis.umn.edu/mapserver" xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:wfs="http://www.opengis.net/wfs/2.0">
  <wfs:member>
    <ms:lokale gml:id="lokale.8033779">
      <ms:GEOMETRIA><gml:Point srsName="urn:ogc:def:crs:EPSG::2180"><gml:pos>251175.68 562852.33</gml:pos></gml:Point></ms:GEOMETRIA>
      <ms:TERYT>1261</ms:TERYT>
      <ms:DOK_OZNACZENIE>1677/2021</ms:DOK_OZNACZENIE>
      <ms:DOK_DATA><gml:TimeInstant><gml:timePosition>2021-09-03</gml:timePosition></gml:TimeInstant></ms:DOK_DATA>
      <ms:DOK_TWORCA>NOT.OLIMPIA DUDKA</ms:DOK_TWORCA>
      <ms:TRAN_RODZAJ_RYNKU>rynekWtorny</ms:TRAN_RODZAJ_RYNKU>
      <ms:TRAN_RODZAJ_TRANS>wolnyRynek</ms:TRAN_RODZAJ_TRANS>
      <ms:TRAN_CENA_BRUTTO>694000</ms:TRAN_CENA_BRUTTO>
      <ms:LOK_CENA_BRUTTO></ms:LOK_CENA_BRUTTO>
      <ms:LOK_POW_UZYT>96.73</ms:LOK_POW_UZYT>
      <ms:LOK_LICZBA_IZB>4</ms:LOK_LICZBA_IZB>
      <ms:LOK_NR_KOND>2</ms:LOK_NR_KOND>
      <ms:LOK_FUNKCJA>mieszkalna</ms:LOK_FUNKCJA>
      <ms:NIER_UDZIAL>1/1</ms:NIER_UDZIAL>
      <ms:LOK_ADRES>MSC:Modlnica;UL:Zakątek;NR_PORZ:7</ms:LOK_ADRES>
    </ms:lokale>
  </wfs:member>
</wfs:FeatureCollection>""".encode()


class TestParseFlatSales(unittest.TestCase):

    def test_a_flat_sale_is_read_with_its_position_in_easting_northing_order(self):
        sale = next(parse_flat_sales(_DOCUMENT))

        self.assertEqual(8033779, sale.id)
        self.assertEqual(datetime(2021, 9, 3), sale.transaction_date)
        self.assertEqual(694_000, sale.transaction_price)
        self.assertIsNone(sale.unit_price)
        self.assertEqual(96.73, sale.area_value)
        self.assertEqual((4, 2), (sale.rooms, sale.floor))
        self.assertEqual((562852.33, 251175.68), (sale.easting, sale.northing))
        self.assertEqual("1677/2021|2021-09-03|NOT.OLIMPIA DUDKA", sale.transaction_key)


class TestTiles(unittest.TestCase):

    def test_tiles_cover_the_bounds_without_overlap(self):
        cut = list(tiles((0, 0, 5000, 3000), tile_m=2000))

        self.assertEqual(6, len(cut))
        self.assertEqual((4000, 2000, 5000, 3000), cut[-1])


if __name__ == "__main__":
    unittest.main()
