#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T api python -m api.seed_neo4j
