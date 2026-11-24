"""Lab-only command; run while the Kafka history consumer is stopped."""
from lab.read_model import QueryStore

store = QueryStore()
store.ensure_schema()
store.reset()
print("Cleared derived MongoDB history documents; source Event Stores untouched")
