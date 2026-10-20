#!/bin/sh
# Runs from the nginx image's /docker-entrypoint.d at container start.
#
# The dashboard's API URL is otherwise fixed at image build time
# (VITE_API_URL). This writes /config.js from AICONTROL_API_URL so the same
# published image works for any deployment: another host, a reverse proxy, or
# the bundled same-origin proxy ("/api"). With no value, the build-time default
# applies.
set -e

DIR="${AICONTROL_CONFIG_DIR:-/usr/share/nginx/html}"
URL="${AICONTROL_API_URL:-}"

if [ -n "$URL" ]; then
  # The value is written into a JavaScript string literal.
  case "$URL" in
    *[!A-Za-z0-9:/._@%~-]*)
      echo "aicontrol: AICONTROL_API_URL contains unsupported characters: $URL" >&2
      exit 1
      ;;
  esac
  printf 'window.__AICONTROL_CONFIG__ = { apiUrl: "%s" };\n' "$URL" > "$DIR/config.js"
else
  printf 'window.__AICONTROL_CONFIG__ = {};\n' > "$DIR/config.js"
fi
