import imaplib
import email
import locale
from datetime import datetime

from Config.Config import HOST, IMAP_PORT
from Database.Connection import DAO


class IMAP:
    def __init__(self):
        self.dao = DAO()

    def get_inbox(self, user_email=None, user_password=None):
        mail = imaplib.IMAP4(host=HOST, port=IMAP_PORT)
        mail.login(user_email, user_password)
        mail.select("INBOX", readonly=True)

        _, search_data = mail.search(None, 'ALL')

        messages = []
        for number in search_data[0].split():
            email_data = {}

            index = number.decode()
            email_data['index'] = index[len(index) - 1].replace(")", "")

            self.add_flags(number, user_email, user_password, context=['Inbox'])

            _, flags_data = mail.fetch(number, '(FLAGS)')
            flags_bytes = flags_data[0]
            flags = email.message_from_bytes(flags_bytes)

            email_flags = self.get_flags(flags)

            for flag in dict.keys(email_flags):
                email_data[flag] = email_flags[flag]

            _, data = mail.fetch(number, '(BODY.PEEK[])')
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
            if email_flags['context'] == 'send':
                email_data['name'] = self.get_user_name(email_data['to'])
            else:
                email_data['name'] = self.get_user_name(email_data['from'])
            messages.append(email_data)

        mail.close()
        mail.logout()

        return messages

    def get_user_name(self, user_email):
        username = "{0}".format(self.dao.get_user(user_email))
        username = username.replace("[", "")
        username = username.replace("]", "")
        username = username.replace("(", "")
        username = username.replace(")", "")
        username = username.replace("'", "")
        username = username.replace(",", "")
        return username

    def get_flags(self, flags):
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

    def add_flags(self, uid, user_email, user_password, context=None, box='INBOX'):
        mail = imaplib.IMAP4(host=HOST, port=IMAP_PORT)
        mail.login(user_email, user_password)
        mail.select(box)

        # add the flags to the message
        if box == 'INBOX':
            mail.store(uid, '+FLAGS', "Inbox")
        if 'Archive' in context:
            mail.store(uid, '+FLAGS', "Archive")
        if 'Important' in context:
            mail.store(uid, '+FLAGS', "Important")

        mail.close()
        mail.logout()

    def delete_email(self, uid, user_email, user_password, box='Inbox'):
        mail = imaplib.IMAP4(host=HOST, port=IMAP_PORT)
        mail.login(user_email, user_password)
        mail.select(box)

        mail.store(uid, '+FLAGS', '\\Deleted')
        mail.expunge()

        mail.close()
        mail.logout()
