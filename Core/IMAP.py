import email
import imaplib

from Config.Config import HOST, IMAP_PORT
from Database.Connection import DAO


def get_flags(flags):
    email_flags = {}
    if "\\Seen" in str(flags):
        email_flags['read'] = True
    else:
        email_flags['read'] = False
    if "Inbox" in str(flags):
        email_flags['context'] = 'inbox'
    if "Sent" in str(flags):
        email_flags['context'] = 'send'
    if "Important" in str(flags):
        email_flags['important'] = True
    else:
        email_flags['important'] = False
    if "Archive" in str(flags):
        email_flags['archive'] = True
    else:
        email_flags['archive'] = False
    return email_flags


class IMAP:

    def __init__(self, user_email, user_password):
        self.dao = None
        self.users = []
        self.mail = imaplib.IMAP4(host=HOST, port=IMAP_PORT)
        self.mail.login(user_email, user_password)

    def get_inbox(self):
        self.mail.select("INBOX", readonly=True)
        self.dao = DAO()
        self.users = self.dao.get_users()
        _, search_data = self.mail.search(None, 'ALL')

        messages = []
        for number in search_data[0].split():
            email_data = {}

            index = number.decode()
            email_data['index'] = index[len(index) - 1].replace(")", "")

            self.add_flags(number, context=['Inbox'])

            _, flags_data = self.mail.fetch(number, '(FLAGS)')
            flags_bytes = flags_data[0]
            flags = email.message_from_bytes(flags_bytes)

            email_flags = get_flags(flags)

            for flag in dict.keys(email_flags):
                email_data[flag] = email_flags[flag]

            _, data = self.mail.fetch(number, '(BODY.PEEK[])')
            _, bytes = data[0]
            email_messages = email.message_from_bytes(bytes)

            for header in ['subject', 'to', 'from', 'date']:
                email_data[header] = email_messages[header]

            for part in email_messages.walk():
                if part.get_content_type() == "text/utf-8" or part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True)
                    email_data['message'] = body.decode()
                elif part.get_content_type() == "text/html":
                    html_body = part.get_payload(decode=True)
                    email_data['message'] = html_body.decode()
                email_data['to_name'] = self.get_user_name(email_data['to'])
                email_data['from_name'] = self.get_user_name(email_data['from'])
            messages.append(email_data)

        return messages

    def get_user_name(self, user_email):
        username = ""
        for user in self.users:
            if user_email == user[1]:
                username = user[0]
                break
        return username

    def add_flags(self, uid, context=None):
        self.mail.select("INBOX")
        # add the flags to the message
        if 'Inbox' in context:
            self.mail.store(uid, '+FLAGS', "Inbox")
        if 'Archive' in context:
            self.mail.store(uid, '+FLAGS', "Archive")
        if 'Important' in context:
            self.mail.store(uid, '+FLAGS', "Important")
        if 'Read' in context:
            self.mail.store(uid, '+FLAGS', "\\Seen")

    def remove_flags(self, uid, context=None):
        self.mail.select("INBOX")

        if 'Archive' in context:
            self.mail.store(uid, '-FLAGS', "Archive")
        if 'Important' in context:
            self.mail.store(uid, '-FLAGS', "Important")
        if 'Read' in context:
            self.mail.store(uid, '-FLAGS', "\\Seen")

    def delete_email(self, uid):
        self.mail.select("INBOX")
        self.mail.store(uid, '+FLAGS', '\\Deleted')
        self.mail.expunge()

    def close(self):
        self.mail.close()
        self.mail.logout()
