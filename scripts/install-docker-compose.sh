#!/bin/bash
# Run with: sudo ./install-docker-compose.sh

set -e

COMPOSE_VERSION="v2.32.4"

echo "=== Downloading Docker Compose ${COMPOSE_VERSION} ==="
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose

echo '=== Setting permissions ==='
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

echo -e '\n=== Verifying ==='
docker compose version

echo -e '\nDone!'
