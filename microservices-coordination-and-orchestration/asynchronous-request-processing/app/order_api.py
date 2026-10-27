"""Composition root for the HTTP adapter (keeps Docker entry point stable)."""
from app.adapters.inbound.http_api import app, repository

def main():
    repository.initialize()
    app.run(host="0.0.0.0", port=5001, use_reloader=False)

if __name__ == "__main__":
    main()
