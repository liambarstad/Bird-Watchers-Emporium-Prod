#!/usr/bin/env bash
set -euo pipefail

UPDATE_FROM_DUMP="${UPDATE_FROM_DUMP:-0}"
DUMPFILE_PATH="${DUMPFILE_PATH:-}"
DB_NAME="${DB_NAME:-neo4j}"
DATA_DIR="${DATA_DIR:-/data}"

export NEO4J_dbms_default__database="$DB_NAME"

if [[ "$UPDATE_FROM_DUMP" == "1" ]]; then
  if [[ -z "$DUMPFILE_PATH" ]]; then
    echo "ERROR: DUMPFILE_PATH is required when UPDATE_FROM_DUMP=1" >&2
    exit 1
  fi
  if [[ ! -e "$DUMPFILE_PATH" ]]; then
    echo "ERROR: UPDATE_FROM_DUMP=1 but dump path does not exist: $DUMPFILE_PATH" >&2
    echo "DEBUG: listing parent dir $(dirname "$DUMPFILE_PATH"):" >&2
    ls -lah "$(dirname "$DUMPFILE_PATH")" >&2 || true
    exit 1
  fi
  if [[ ! -f "$DUMPFILE_PATH" ]]; then
    echo "ERROR: UPDATE_FROM_DUMP=1 but dump path is not a regular file: $DUMPFILE_PATH" >&2
    ls -lah "$DUMPFILE_PATH" >&2 || true
    exit 1
  fi
  if [[ ! -r "$DUMPFILE_PATH" ]]; then
    echo "ERROR: UPDATE_FROM_DUMP=1 but dump file is not readable by this container user: $DUMPFILE_PATH" >&2
    echo "DEBUG: id:" >&2
    id >&2 || true
    echo "DEBUG: ls -lah $DUMPFILE_PATH:" >&2
    ls -lah "$DUMPFILE_PATH" >&2 || true
    exit 1
  fi
  mkdir -p "$DATA_DIR"
  echo "DEBUG: dump file details:" >&2
  ls -lah "$DUMPFILE_PATH" >&2 || true
  if command -v sha256sum >/dev/null 2>&1; then
    echo "DEBUG: sha256(dump):" >&2
    sha256sum "$DUMPFILE_PATH" >&2 || true
  fi
  echo "Loading database '$DB_NAME' into $DATA_DIR from dump $DUMPFILE_PATH"
  # Neo4j 5.x uses --from-stdin/--from-path (no --from). Using stdin allows arbitrary dump filenames.
  neo4j-admin database load "$DB_NAME" --from-stdin --overwrite-destination --verbose < "$DUMPFILE_PATH"
else
  if [[ ! -d "$DATA_DIR/databases/$DB_NAME" ]]; then
    echo "ERROR: UPDATE_FROM_DUMP=0 but database directory not found at $DATA_DIR/databases/$DB_NAME" >&2
    exit 1
  fi
  echo "Using existing database at $DATA_DIR/databases/$DB_NAME"
fi

echo "Starting Neo4j with database '$DB_NAME'"
exec /startup/docker-entrypoint.sh neo4j

