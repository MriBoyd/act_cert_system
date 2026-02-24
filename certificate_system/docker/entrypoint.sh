#!/usr/bin/env sh
set -e

cd /app

# Wait briefly for DB DNS to resolve (compose handles healthcheck too).

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
