import os

from flask import Flask, request

from adapters import DiscountCatalog, HttpCatalog, MemoryCatalog
from domain import quote

app = Flask(__name__)


def build_catalog():
    backend = os.getenv("CATALOG_BACKEND", "memory")

    if backend == "memory":
        return backend, MemoryCatalog()
    if backend == "discount":
        return backend, DiscountCatalog()
    if backend == "http":
        return backend, HttpCatalog(os.getenv("CATALOG_URL", "http://catalog:5000"))

    raise ValueError(f"unsupported CATALOG_BACKEND: {backend}")


CATALOG_BACKEND, catalog = build_catalog()


@app.route("/quote")
def get_quote():
    try:
        result = quote(catalog, 1, int(request.args.get("quantity", "2")))
        result["catalog_backend"] = CATALOG_BACKEND
        return result
    except ValueError as error:
        return {"error": str(error)}, 400
    except (OSError, KeyError):
        return {"error": "catalog unavailable"}, 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
