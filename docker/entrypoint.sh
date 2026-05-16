#!/bin/sh
# Container entrypoint.
#
# Named docker volumes mount root-owned by default. The runtime user
# (uid 1000) cannot write to them, which breaks ChromaDB's
# `PersistentClient` init and the upload spool. We fix permissions here
# at container start and then drop privileges to `app` for the actual
# process — keeps the runtime non-root per the constitution's security
# rules.
set -eu

for dir in /app/chroma_data /app/uploads_tmp; do
    mkdir -p "$dir"
    chown -R app:app "$dir" 2>/dev/null || true
done

exec runuser -u app -- "$@"
