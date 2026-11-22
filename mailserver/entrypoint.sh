#!/bin/bash
# Renders the configuration templates from environment variables and starts
# Dovecot (daemon) and Postfix (foreground, PID 1 child).
set -euo pipefail

: "${MAIL_DOMAIN:?MAIL_DOMAIN is required}"
: "${DB_HOST:?DB_HOST is required}"
: "${DB_NAME:?DB_NAME is required}"
: "${MAILSERVER_DB_PASSWORD:?MAILSERVER_DB_PASSWORD is required}"
: "${MASTER_USER:?MASTER_USER is required}"
: "${MASTER_PASSWORD:?MASTER_PASSWORD is required}"

VARS='${MAIL_DOMAIN} ${DB_HOST} ${DB_NAME} ${MAILSERVER_DB_PASSWORD}'
render() { envsubst "$VARS" < "$1" > "$2"; }

# --- Dovecot -------------------------------------------------------------------
render /etc/postoffice/dovecot/dovecot.conf /etc/dovecot/dovecot.conf
render /etc/postoffice/dovecot/dovecot-sql.conf.ext /etc/dovecot/dovecot-sql.conf.ext
chmod 0600 /etc/dovecot/dovecot-sql.conf.ext
echo "${MASTER_USER}:$(doveadm pw -s BLF-CRYPT -p "${MASTER_PASSWORD}")" > /etc/dovecot/master-users
chown dovecot:dovecot /etc/dovecot/master-users
chmod 0600 /etc/dovecot/master-users
chown -R vmail:vmail /var/mail/vhosts

# --- Postfix -------------------------------------------------------------------
render /etc/postoffice/postfix/main.cf /etc/postfix/main.cf
for map in mysql-virtual-mailbox-maps.cf mysql-sender-login-maps.cf; do
  render "/etc/postoffice/postfix/${map}" "/etc/postfix/${map}"
  chown root:postfix "/etc/postfix/${map}"
  chmod 0640 "/etc/postfix/${map}"
done
if ! grep -q '^submission' /etc/postfix/master.cf; then
  cat /etc/postoffice/postfix/master-submission.cf >> /etc/postfix/master.cf
fi
# Run every Postfix service outside the chroot so MariaDB lookups resolve.
postconf -F '*/*/chroot = n'
cp /etc/resolv.conf /etc/hosts /var/spool/postfix/etc/ 2>/dev/null || true
newaliases

dovecot
exec postfix start-fg
