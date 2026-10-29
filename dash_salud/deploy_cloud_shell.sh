#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-eda-salud-atlantico-2018}"
REGION="${REGION:-us-east1}"
SERVICE_NAME="${SERVICE_NAME:-dataviz-salud-atlantico}"

cd "$(dirname "$0")"
for path in data/eda.json data/modelo.json informe/index.html; do
  if [[ ! -f "$path" ]]; then
    echo "Falta $path: sube el paquete completo del panel y del Bookdown." >&2
    exit 1
  fi
done

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  --project "$PROJECT_ID"
gcloud run deploy "$SERVICE_NAME" \
  --project "$PROJECT_ID" --region "$REGION" --source . \
  --platform managed --allow-unauthenticated --port 8080 \
  --cpu 1 --memory 512Mi --min-instances 0 --max-instances 3 \
  --concurrency 40
