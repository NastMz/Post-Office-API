import imaplib
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from Config.Config import HOST, SMTP_PORT, IMAP_PORT


class SMTP:
    def send_email(self, html=None, text='Email body', subject='Email subject', from_email=None, to_emails=None,
                   password=None):
        assert isinstance(to_emails, list)
        msg = MIMEMultipart('alternative')
        msg['From'] = from_email
        msg['To'] = ", ".join(to_emails)
        msg['Subject'] = subject
        msg['Date'] = imaplib.Time2Internaldate(time.time())

        txt_part = MIMEText(text, 'utf-8')
        msg.attach(txt_part)

        if html is not None:
            html_part = MIMEText(html, 'html')
            msg.attach(html_part)

        msg_str = msg.as_string()

        # Login to my smtp server
        server = smtplib.SMTP(host=HOST, port=SMTP_PORT)
        server.ehlo()
        server.login(from_email, password)
        server.sendmail(from_email, to_emails, msg_str)
        server.quit()

        # save sent email
        mail = imaplib.IMAP4(host=HOST, port=IMAP_PORT)
        mail.login(from_email, password)
        mail.append(mailbox='INBOX', flags='Sent', date_time=imaplib.Time2Internaldate(time.time()), message=msg_str.encode('utf8'))
        mail.logout()


#
# send_email(text='This is an email from python', subject='Email from python', from_email=user_email,
#            to_emails=['test1@massmail.site'])
