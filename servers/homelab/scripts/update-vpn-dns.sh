#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_TAG="update-vpn-dns"
source "$SCRIPT_DIR/.env"

az login --service-principal \
  --username "$AZURE_CLIENT_ID" \
  --password "$AZURE_CLIENT_SECRET" \
  --tenant "$AZURE_TENANT_ID" \
  --output none

logger -t "$LOG_TAG" "INFO: Logged into Azure"

CURRENT_IP=$(curl -s https://api.ipify.org)
logger -t "$LOG_TAG" "INFO: Current IP is: $CURRENT_IP"

RECORD_IP=$(az network dns record-set a show \
  --resource-group "$RG" \
  --zone-name "$ZONE_NAME" \
  --name "$RECORD_NAME" \
  --query ARecords[0].ipv4Address -o tsv)

logger -t "$LOG_TAG" "INFO: Record IP is: ${RECORD_IP:-"No IP found"}"

if [ "$CURRENT_IP" != "$RECORD_IP" ]; then
    az network dns record-set a update \
      --resource-group "$RG" \
      --zone-name "$ZONE_NAME" \
      --name "$RECORD_NAME" \
      --set ARecords[0].ipv4Address="$CURRENT_IP"
    logger -t "$LOG_TAG" "SUCCESS: Updated DNS to $CURRENT_IP"
else
    logger -t "$LOG_TAG" "INFO: No change required"
fi

az logout --output none
logger -t "$LOG_TAG" "INFO: Logged out of Azure"