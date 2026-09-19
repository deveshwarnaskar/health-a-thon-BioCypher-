#!/usr/bin/env bash
# scripts/detect_lan_ip.sh
# Discovers local network IPv4 address for mobile physical device testing.
set -euo pipefail

LAN_IP=""
if [[ "$OSTYPE" == "darwin"* ]]; then
  LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
fi

if [[ -z "$LAN_IP" ]]; then
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
fi

if [[ -z "$LAN_IP" ]]; then
  LAN_IP="127.0.0.1"
fi

echo "=================================================================="
echo "THALI x P.L.A.T.E. - LAN Development IP Discovery"
echo "=================================================================="
echo "Detected LAN IP: $LAN_IP"
echo ""
echo "For physical mobile device testing, update your apps/mobile/.env:"
echo "  EXPO_PUBLIC_API_BASE_URL=http://${LAN_IP}:8000"
echo "  EXPO_PUBLIC_KEYCLOAK_ISSUER_URL=http://${LAN_IP}:8080/realms/thali"
echo ""
echo "Ensure your firewall allows incoming traffic on ports 8000 and 8080."
echo "=================================================================="
