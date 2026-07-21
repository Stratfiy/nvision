#!/usr/bin/env bash
# One-shot .env generator for an NVision deployment.
#
# Generates the encryption + worker secrets, detects this host's public IP
# (works out of the box on EC2 — picks up an associated Elastic IP), and wires
# up REACT_APP_BACKEND_URL. Leaves GEMINI_API_KEY blank on purpose: add it in
# the web UI under Settings -> BYO Provider Keys -> Google Gemini.
#
# Usage:
#   bash scripts/setup-env.sh                # auto-detect public IP (EC2)
#   bash scripts/setup-env.sh 1.2.3.4        # or pass your Elastic IP explicitly
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  cp .env .env.bak
  echo "Existing .env backed up to .env.bak"
fi
cp .env.example .env

MASTER_KEY=$(openssl rand -base64 32 | tr '+/' '-_')
WORKER_TOKEN=$(openssl rand -hex 16)

PUBIP="${1:-}"
if [ -z "$PUBIP" ]; then
  TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 120" 2>/dev/null || true)
  PUBIP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
fi
if [ -z "$PUBIP" ]; then
  echo "WARNING: could not auto-detect a public IP; defaulting to localhost."
  echo "         Re-run with your address:  bash scripts/setup-env.sh <ELASTIC_IP>"
  PUBIP="localhost"
fi

sed -i "s|^NVISION_MASTER_KEY=.*|NVISION_MASTER_KEY=${MASTER_KEY}|" .env
sed -i "s|^WORKER_TOKEN=.*|WORKER_TOKEN=${WORKER_TOKEN}|" .env
sed -i "s|^REACT_APP_BACKEND_URL=.*|REACT_APP_BACKEND_URL=http://${PUBIP}:8000|" .env

echo
echo "==> .env configured:"
echo "    NVISION_MASTER_KEY   = <generated, kept in .env>"
echo "    WORKER_TOKEN         = <generated, kept in .env>"
echo "    REACT_APP_BACKEND_URL= http://${PUBIP}:8000"
echo "    GEMINI_API_KEY       = (blank — add it in the web UI)"
echo
echo "Next:"
echo "    docker compose up -d --build"
echo "    open  http://${PUBIP}:3000   (ensure security group allows TCP 3000 and 8000)"
echo "    then  Settings -> BYO Provider Keys -> Google Gemini -> paste your key"
