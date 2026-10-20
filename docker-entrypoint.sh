#!/bin/sh
# AIControl API container entrypoint.
#
# Applies pending database migrations before starting the app so that pulling a
# new image and restarting is a complete upgrade. Set RUN_MIGRATIONS=false to
# manage migrations yourself (e.g. a separate release step, or more than one
# API process, since two migrators racing on the same database is unsafe).
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "aicontrol: applying database migrations"
  alembic upgrade head
fi

exec "$@"
