from flask import Flask, jsonify, request
from flask_cors import CORS

from Core.IMAP import IMAP
from Core.SMTP import SMTP
from Core.Login import Login
from Core.Register import Register
from Database.Users import Users
from Utils.JWT import token_required, validate_token

app = Flask(__name__)
CORS(app)


@app.route('/api/inbox', methods=['GET'])
@token_required
def inbox(data):
    imap = IMAP()
    u_email = data['email']
    u_password = data['pass']
    mails = imap.get_inbox(u_email, u_password)
    if len(mails) > 0:
        return jsonify({"emails": mails})
    else:
        return jsonify({"message": "Inbox is empty"})


@app.route('/api/send', methods=['POST'])
@token_required
def send(data):
    smtp = SMTP()
    new_email = {
        "from": data['email'],
        "to": request.json['to'],
        "subject": request.json['subject'],
        "text": request.json['text'],
        "pass": data['pass']
    }
    smtp.send_email(text=new_email['text'],
                    subject=new_email['subject'],
                    from_email=new_email['from'],
                    to_emails=[new_email['to']],
                    password=new_email['pass'])
    return jsonify({"message": "Email sent successfully!"})


@app.route('/api/delete', methods=['POST'])
@token_required
def delete(data):
    imap = IMAP()
    u_email = data['email']
    u_password = data['pass']
    uid = request.json['index']
    imap.delete_email(uid, u_email, u_password)
    return jsonify({"message": "Email delete successfully!"})


@app.route('/api/archive', methods=['POST'])
@token_required
def mark_as_archived(data):
    imap = IMAP()
    u_email = data['email']
    u_password = data['pass']
    uid = request.json['index']
    imap.add_flags(uid, u_email, u_password, context=['Archive'])
    return jsonify({"message": "Email archived successfully!"})


@app.route('/api/important', methods=['POST'])
@token_required
def mark_as_important(data):
    imap = IMAP()
    u_email = data['email']
    u_password = data['pass']
    uid = request.json['index']
    imap.add_flags(uid, u_email, u_password, context=['Important'])
    return jsonify({"message": "Email marked as important successfully!"})


@app.route('/api/users', methods=['GET'])
@token_required
def users(data):
    u = Users()
    return jsonify({"users": u.get_users()})


@app.route('/api/login', methods=['POST'])
def login():
    _login = Login()
    return jsonify(_login.verify_crendentials(request.json['email'], request.json['pass']))


@app.route('/api/register', methods=['POST'])
def register():
    _register = Register()
    return jsonify(
        {"message": _register.register_user(request.json['email'], request.json['pass'], request.json['fname'])})


@app.route('/api/validate', methods=['GET'])
def validate():
    token = request.headers['Authorization']
    token = token.replace("Bearer ", "")
    return validate_token(token)


if __name__ == '__main__':
    app.run(debug=True, port=4000)
