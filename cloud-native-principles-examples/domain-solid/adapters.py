import json
import urllib.request

from domain import PriceCatalog


class MemoryCatalog(PriceCatalog):
    def price_cents(self, product_id):
        return {1: 1200}[product_id]


class DiscountCatalog(PriceCatalog):
    def price_cents(self, product_id):
        return {1: 1000}[product_id]


class HttpCatalog(PriceCatalog):
    def __init__(self, base_url):
        self.base_url = base_url

    def price_cents(self, product_id):
        with urllib.request.urlopen(
            f"{self.base_url}/products/{product_id}", timeout=1
        ) as response:
            return json.load(response)["price_cents"]
