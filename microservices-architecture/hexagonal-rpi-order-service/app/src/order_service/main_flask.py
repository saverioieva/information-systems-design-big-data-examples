from flask import Flask, jsonify

from order_service.adapters.inbound.flask.routes import build_order_blueprint
from order_service.adapters.outbound.postgres.repository import PostgresOrderRepository
from order_service.application.services.order_service import OrderApplicationService
from order_service.infrastructure.database import SessionFactory, create_schema


def create_app() -> Flask:
    """Composition root for the Flask inbound adapter."""

    create_schema()

    repository = PostgresOrderRepository(SessionFactory)
    order_service = OrderApplicationService(repository)

    app = Flask(__name__)
    app.register_blueprint(build_order_blueprint(order_service))

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "adapter": "flask"})

    return app


app = create_app()
