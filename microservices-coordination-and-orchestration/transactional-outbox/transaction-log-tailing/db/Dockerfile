# The official PostgreSQL image plus the wal2json logical decoding plugin.
# PostgreSQL's built-in pgoutput is binary and would need a separate decoder.
FROM postgres:16-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-16-wal2json \
 && rm -rf /var/lib/apt/lists/*
