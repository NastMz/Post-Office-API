from flask import Flask, jsonify, request

from Core.IMAP import IMAP
from Core.SMTP import SMTP
from Core.login import Login
from Core.register import Register

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


@app.route('/login', methods=['POST'])
def login():
    login = Login()
    return jsonify({"message": login.verify_crendentials(request.json['email'], request.json['pass'])})

@app.route('/register', methods=['POST'])
def register():
    register = Register()
    return jsonify({"message": register.register_user(request.json['email'], request.json['pass'], request.json['fname'])})

if __name__ == '__main__':
    app.run(debug=True, port=4000)
