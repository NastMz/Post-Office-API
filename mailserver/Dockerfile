# Mail transfer + delivery agent for the Post Office stack.
#   Postfix  : SMTP (25) and authenticated submission (587)
#   Dovecot  : IMAP (143), LMTP local delivery and SASL auth for Postfix
FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      postfix postfix-mysql \
      dovecot-core dovecot-imapd dovecot-lmtpd dovecot-mysql \
      gettext-base ca-certificates netcat-openbsd \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -g 5000 vmail \
 && useradd -u 5000 -g vmail -d /var/mail/vhosts -s /usr/sbin/nologin vmail \
 && mkdir -p /var/mail/vhosts \
 && chown -R vmail:vmail /var/mail/vhosts

COPY postfix/ /etc/postoffice/postfix/
COPY dovecot/ /etc/postoffice/dovecot/
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 25 587 143
VOLUME ["/var/mail/vhosts"]

HEALTHCHECK --interval=5s --timeout=3s --retries=30 \
  CMD nc -z localhost 143 && nc -z localhost 587 || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
