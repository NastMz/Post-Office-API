from flask import Flask, jsonify, request
from flask_cors import CORS

from Core.IMAP import IMAP
from Core.SMTP import SMTP
from Core.Login import Login
from Core.Register import Register
from Database.Users import Users
from Utils.JWT import token_required, get_payload

app = Flask(__name__)
CORS(app)


@app.route('/api/inbox', methods=['GET'])
@token_required
def inbox(data):
    imap = IMAP(data['email'], data['pass'])
    mails = imap.get_inbox()
    imap.close()
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


@app.route('/api/delete', methods=['DELETE'])
@token_required
def delete(data):
    imap = IMAP(data['email'], data['pass'])
    uid = request.json['index']
    imap.delete_email(uid)
    imap.close()
    return jsonify({"message": "Email delete successfully!"})


@app.route('/api/archive', methods=['PUT'])
@token_required
def mark_as_archived(data):
    imap = IMAP(data['email'], data['pass'])
    uid = request.json['index']
    imap.add_flags(uid, context=['Archive'])
    imap.close()
    return jsonify({"message": "Email archived successfully!"})


@app.route('/api/important', methods=['PUT'])
@token_required
def mark_as_important(data):
    imap = IMAP(data['email'], data['pass'])
    uid = request.json['index']
    imap.add_flags(uid, context=['Important'])
    imap.close()
    return jsonify({"message": "Email marked as important successfully!"})


@app.route('/api/read', methods=['PUT'])
@token_required
def mark_as_read(data):
    imap = IMAP(data['email'], data['pass'])
    uid = request.json['index']
    imap.add_flags(uid, context=['Read'])
    imap.close()
    return jsonify({"message": "Email marked as read successfully!"})


@app.route('/api/unmark/archive', methods=['PUT'])
@token_required
def unmark_as_archived(data):
    imap = IMAP(data['email'], data['pass'])
    uid = request.json['index']
    imap.remove_flags(uid, context=['Archive'])
    imap.close()
    return jsonify({"message": "Email unarchived successfully!"})


@app.route('/api/unmark/important', methods=['PUT'])
@token_required
def unmark_as_important(data):
    imap = IMAP(data['email'], data['pass'])
    uid = request.json['index']
    imap.remove_flags(uid, context=['Important'])
    imap.close()
    return jsonify({"message": "Email unmarked as important successfully!"})


@app.route('/api/unmark/read', methods=['PUT'])
@token_required
def unmark_as_read(data):
    imap = IMAP(data['email'], data['pass'])
    uid = request.json['index']
    imap.remove_flags(uid, context=['Read'])
    imap.close()
    return jsonify({"message": "Email unmarked as read successfully!"})


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
        {"message": _register.register_user(request.json['email'], request.json['pass'], request.json['name'])})


@app.route('/api/payload', methods=['GET'])
def payload():
    token = request.headers['Authorization']
    token = token.replace("Bearer ", "")
    email = get_payload(token)
    u = Users()
    name = u.get_user(email)
    return jsonify({'name': name[0][0], 'email': email})


if __name__ == '__main__':
    app.run()
