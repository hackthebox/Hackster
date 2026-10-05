#!/bin/sh

DB_WAIT_TIMEOUT_SECONDS="${DB_WAIT_TIMEOUT_SECONDS:-60}"

if [ -f "/vault/secrets/.env" ]
then
  set -a
  # Load Vault-rendered environment variables using shell parsing instead of xargs.
  . /vault/secrets/.env
  set +a
  ln -sf /vault/secrets/.env .env
fi

db_waited=0
while ! mysqladmin ping --skip-ssl -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" --silent; do
  echo 'Database not ready yet'
  db_waited=$((db_waited + 1))
  if [ "$db_waited" -ge "$DB_WAIT_TIMEOUT_SECONDS" ]; then
    echo "Database did not become ready within ${DB_WAIT_TIMEOUT_SECONDS}s; exiting"
    exit 1
  fi
  sleep 1
done

# Run migrations & start the bot
alembic upgrade head && exec uv run --no-sync task start
