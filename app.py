from flask import Flask, jsonify, request

from Core.IMAP import IMAP
from Core.SMTP import SMTP

app = Flask(__name__)


@app.route('/inbox', methods=['GET'])
def inbox():
    imap = IMAP()
    u_email = 'test2@massmail.site'
    u_password = 'test2'
    mails = imap.get_inbox(u_email, u_password)
    if len(mails) > 0:
        return jsonify({"inbox": mails})
    else:
        return jsonify({"message": "Invalid email!"})


@app.route('/send', methods=['POST'])
def send():
    smpt = SMTP()
    new_email = {
        "from": request.json['from'],
        "to": request.json['to'],
        "subject": request.json['subject'],
        "text": request.json['text'],
        "pass": request.json['pass']
    }
    smpt.send_email(text=new_email['text'],
                    subject=new_email['subject'],
                    from_email=new_email['from'],
                    to_emails=[new_email['to']],
                    password=new_email['pass'])
    return jsonify({"message": "Email sent successfully!"})


if __name__ == '__main__':
    app.run(debug=True, port=4000)
