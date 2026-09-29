class PriceCatalog:
    def price_cents(self, product_id):
        raise NotImplementedError


def quote(catalog, product_id, quantity):
    if type(quantity) is not int or quantity < 1:
        raise ValueError("quantity must be a positive integer")

    return {
        "product_id": product_id,
        "quantity": quantity,
        "total_cents": catalog.price_cents(product_id) * quantity,
    }
