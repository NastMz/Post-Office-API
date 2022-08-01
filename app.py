from flask import Flask, jsonify, request

from Core.IMAP import IMAP
from Core.SMTP import SMTP

app = Flask(__name__)


@app.route('/inbox', methods=['GET'])
def inbox():
    imap = IMAP()
    u_email = request.json['email']
    u_password = request.json['pass']
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


@app.route('/delete', methods=['POST'])
def delete():
    imap = IMAP()
    u_email = request.json['email']
    u_password = request.json['pass']
    uid = request.json['index']
    imap.delete_email(uid, u_email, u_password)
    return jsonify({"message": "Email delete successfully!"})


@app.route('/archive', methods=['POST'])
def mark_as_archived():
    imap = IMAP()
    u_email = request.json['email']
    u_password = request.json['pass']
    uid = request.json['index']
    imap.add_flags(uid, u_email, u_password, context=['Archive'])
    return jsonify({"message": "Email archived successfully!"})


@app.route('/important', methods=['POST'])
def mark_as_important():
    imap = IMAP()
    u_email = request.json['email']
    u_password = request.json['pass']
    uid = request.json['index']
    imap.add_flags(uid, u_email, u_password, context=['Important'])
    return jsonify({"message": "Email marked as important successfully!"})


if __name__ == '__main__':
    app.run(debug=True, port=4000)
