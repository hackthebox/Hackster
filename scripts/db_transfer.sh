#!/bin/sh
# Copy the Hackster database between servers with a dump file, and check that
# every table arrived with the same row count.
#
#   db_transfer.sh dump FILE      write FILE (gzipped SQL) and FILE.counts
#   db_transfer.sh restore FILE   load FILE into an empty database, then compare
#                                 its row counts with FILE.counts
#
# Connection comes from MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD and
# MYSQL_DATABASE, the same variables the bot reads. MYSQL_PASSWORD may be unset
# for logins that need none (a local socket, an IAM-authenticated tunnel). Stop
# the bot before the dump: rows written after it are lost.
set -eu

usage() {
  echo "usage: $0 dump|restore FILE" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
command="$1"
file="$2"

: "${MYSQL_HOST:?}" "${MYSQL_USER:?}" "${MYSQL_DATABASE:?}"
if [ -n "${MYSQL_PASSWORD:-}" ]; then
  # Read by the client, so the password stays out of the process list.
  export MYSQL_PWD="$MYSQL_PASSWORD"
fi

# Without --port, MYSQL_HOST=localhost goes through the local socket.
connection="--host=$MYSQL_HOST --user=$MYSQL_USER${MYSQL_PORT:+ --port=$MYSQL_PORT}"

# No pipelines below: sh has no pipefail, so a failing client on the left of a
# pipe would go unnoticed and leave an empty dump that looks like a success.
sql() {
  # shellcheck disable=SC2086
  mariadb $connection --batch --skip-column-names "$MYSQL_DATABASE" -e "$1"
}

row_counts() {
  tables="$(sql "SELECT table_name FROM information_schema.tables
                 WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'
                 ORDER BY table_name")"
  for table in $tables; do
    count="$(sql "SELECT COUNT(*) FROM \`$table\`")"
    printf '%s\t%s\n' "$table" "$count"
  done
}

case "$command" in
  dump)
    version="$(sql "SELECT VERSION()")"
    echo "source server: $version"
    # No --databases: the file carries no CREATE DATABASE or USE, so it loads
    # into whatever MYSQL_DATABASE names on the target.
    # shellcheck disable=SC2086
    mariadb-dump $connection \
      --single-transaction --quick --hex-blob --no-tablespaces \
      --default-character-set=utf8mb4 \
      "$MYSQL_DATABASE" > "$file.sql"
    gzip -c "$file.sql" > "$file"
    rm -f "$file.sql"
    row_counts > "$file.counts"
    echo "wrote $file and $file.counts ($(wc -l < "$file.counts" | tr -d ' ') tables)"
    ;;
  restore)
    [ -f "$file.counts" ] || { echo "missing $file.counts" >&2; exit 1; }
    version="$(sql "SELECT VERSION()")"
    echo "target server: $version"
    existing="$(sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()")"
    if [ "$existing" -ne 0 ]; then
      echo "$MYSQL_DATABASE already has $existing tables; refusing to load into a non-empty database" >&2
      exit 1
    fi
    # shellcheck disable=SC2086
    gunzip -c "$file" | mariadb $connection --default-character-set=utf8mb4 "$MYSQL_DATABASE"
    row_counts > "$file.restored"
    if diff -u "$file.counts" "$file.restored"; then
      echo "restore verified: row counts match for $(wc -l < "$file.counts" | tr -d ' ') tables"
    else
      echo "row counts differ (source on the left)" >&2
      exit 1
    fi
    ;;
  *)
    usage
    ;;
esac
