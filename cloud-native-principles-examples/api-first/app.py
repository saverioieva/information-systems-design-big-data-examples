import os

from flask import Flask, jsonify, send_from_directory
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__)

# The OpenAPI file is the API contract. Swagger UI reads this file; it does not
# generate the contract from the Flask implementation.
SWAGGER_URL = "/docs"
OPENAPI_URL = "/openapi.yaml"

swagger_ui = get_swaggerui_blueprint(
    SWAGGER_URL,
    OPENAPI_URL,
    config={"app_name": "Product API - API First / Contract First"},
)
app.register_blueprint(swagger_ui, url_prefix=SWAGGER_URL)


@app.route("/openapi.yaml")
def openapi_contract():
    return send_from_directory(
        app.root_path,
        "openapi.yaml",
        mimetype="application/yaml",
    )


@app.route("/products/1")
def product():
    mode = os.getenv("API_MODE", "v1")
    data = {"id": 1, "name": "Notebook", "price_cents": 1200}

    if mode == "additive":
        # Compatible evolution: existing fields remain available.
        data["currency"] = "EUR"
        data["price_euros"] = data["price_cents"] / 100
    elif mode == "breaking":
        # Deliberately breaks the contract for teaching purposes.
        data["price"] = data.pop("price_cents") / 100

    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
