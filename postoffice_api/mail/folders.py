"""Public folder identifiers mapped to the IMAP mailbox names created by Dovecot."""

from __future__ import annotations

from postoffice_api.errors import not_found

FOLDERS: dict[str, str] = {
    "inbox": "INBOX",
    "sent": "Sent",
    "drafts": "Drafts",
    "archive": "Archive",
    "trash": "Trash",
}


def mailbox_for(folder: str) -> str:
    try:
        return FOLDERS[folder]
    except KeyError:
        raise not_found(f"Unknown folder '{folder}'") from None
