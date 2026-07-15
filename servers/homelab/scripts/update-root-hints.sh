#!/bin/bash
NAMED_ROOT_URL="https://www.internic.net/domain/named.root"
DEST="/opt/homelab/unbound/root.hints"

logger -t "$LOG_TAG" "INFO: Create temp file"
TMP_FILE=$(mktemp)

# Download to temp file first, not directly to destination
logger -t "$LOG_TAG" "INFO: Downloading new root hints"

if ! curl -fsSL --max-time 30 "$NAMED_ROOT_URL" -o "$TMP_FILE"; then
    logger -t "$LOG_TAG" "ERROR: Failed to download named.root"
    rm -f "$TMP_FILE"
    exit 1
fi

if ! grep -q "ROOT-SERVERS.NET" "$TMP_FILE"; then
    logger -t "$LOG_TAG" "ERROR: Downloaded file doesn't look like a valid named.root"
    rm -f "$TMP_FILE"
    exit 1
fi

# Backup existing file
cp "$DEST" "${DEST}.bak"
logger -t "$LOG_TAG" "INFO: Backup created at ${DEST}.bak"

# Only now replace the live file
mv "$TMP_FILE" "$DEST"

logger -t "$LOG_TAG" "SUCCESS: root.hints updated successfully"

# Reload Unbound inside the container dev/null required to enable successful logging
#
if docker restart unbound > /dev/null 2>&1; then
    logger -t "$LOG_TAG" "INFO: Unbound restarted successfully"
else
    logger -t "$LOG_TAG" "ERROR: Failed to restart Unbound"
fi