"""Entrypoint for the external message relay container and slot bootstrap."""
import sys

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in {'init-slot', 'relay'}:
        raise SystemExit('Usage: python -m app.log_tailing init-slot|relay')
    if sys.argv[1] == 'init-slot':
        from app.adapters.inbound.postgres_wal_reader import ensure_slot
        ensure_slot()
    else:
        from app.adapters.inbound.postgres_wal_reader import run
        run()
