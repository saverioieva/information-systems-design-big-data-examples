from flask import Flask, jsonify

from order_service.adapters.inbound.flask.routes import build_order_blueprint
from order_service.bootstrap import build_order_use_cases
from order_service.infrastructure.database import create_schema


def create_app() -> Flask:
    """Composition root for the Flask inbound adapter."""

    create_schema()
    order_service = build_order_use_cases()

    app = Flask(__name__)
    app.register_blueprint(build_order_blueprint(order_service))

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "adapter": "flask"})

    return app


app = create_app()
