#!/bin/bash
# Creates a read-only account for Postfix/Dovecot lookups.
set -euo pipefail
mariadb -uroot -p"${MARIADB_ROOT_PASSWORD}" <<SQL
CREATE USER IF NOT EXISTS 'mailserver'@'%' IDENTIFIED BY '${MAILSERVER_DB_PASSWORD}';
GRANT SELECT ON \`${MARIADB_DATABASE}\`.users TO 'mailserver'@'%';
FLUSH PRIVILEGES;
SQL
