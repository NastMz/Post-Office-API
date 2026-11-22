-- Post Office user directory.
-- Shared by the API (registration, directory) and by the mail server:
-- Postfix uses it to accept mail for existing mailboxes and Dovecot uses it
-- to authenticate IMAP/SMTP logins.
CREATE TABLE IF NOT EXISTS users (
    id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    email       VARCHAR(254)  NOT NULL,
    full_name   VARCHAR(80)   NOT NULL,
    -- Dovecot scheme-prefixed hash, e.g. {BLF-CRYPT}$2b$12$...
    password    VARCHAR(255)  NOT NULL,
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
