import imaplib
import email

from Config.Config import HOST, IMAP_PORT
from Database.Connection import DAO


class IMAP:
    def __init__(self):
        self.dao = DAO()

    def get_inbox(self, user_email=None, user_password=None):
        mail = imaplib.IMAP4(host=HOST, port=IMAP_PORT)
        mail.login(user_email, user_password)
        mail.select("inbox")

        _, search_data = mail.search(None, 'ALL')

        messages = []
        for number in search_data[0].split():
            email_data = {}

            _, data = mail.fetch(number, '(RFC822)')
            _, bytes = data[0]
            email_messages = email.message_from_bytes(bytes)

            _, index_data = mail.fetch(number, 'UID')
            index_bytes = index_data[0]
            email_index = email.message_from_bytes(index_bytes)

            index = email_index.get_payload(decode=True).decode().split()
            email_data['index'] = index[len(index) - 1].replace(")", "")

            for header in ['subject', 'to', 'from', 'date']:
                email_data[header] = email_messages[header]

            for part in email_messages.walk():
                if part.get_content_type() == "text/utf-8" or part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True)
                    email_data['body'] = body.decode()
                elif part.get_content_type() == "text/html":
                    html_body = part.get_payload(decode=True)
                    email_data['body'] = html_body.decode()
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
