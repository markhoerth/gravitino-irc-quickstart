#!/usr/bin/env sh
# minio-init.sh — Standalone bucket setup script (optional, for manual runs).
# The docker-compose minio-setup service handles this automatically.
#
# Usage (from host): docker exec minio-setup /scripts/minio-init.sh
# Or manually:
#   docker run --rm --network gravitino-irc_irc-net \
#     -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin123 \
#     minio/mc /bin/sh -c "$(cat scripts/init/minio-init.sh)"

set -e

MINIO_URL="${MINIO_URL:-http://minio:9000}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin123}"
MINIO_BUCKET="${MINIO_BUCKET:-warehouse}"

mc alias set minio "${MINIO_URL}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
mc mb --ignore-existing "minio/${MINIO_BUCKET}"
mc anonymous set download "minio/${MINIO_BUCKET}"

echo "✓ Bucket '${MINIO_BUCKET}' ready at ${MINIO_URL}"
mc ls "minio/${MINIO_BUCKET}"
