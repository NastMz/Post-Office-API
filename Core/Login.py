import base64
import binascii
import hashlib

import jwt

from Config.Config import KEY
from Database.Connection import DAO


class Login:
    def __init__(self):
        self.dao = DAO()

    def verify_crendentials(self, user_email, user_password):
        exist_mail = self.dao.get_email(user_email)
        status = {"message": "!Correo y/o contraseña incorrecto!"}
        if exist_mail:
            user = self.dao.get_credential(user_email)
            if len(user) > 0:
                encrypted_pass = hashlib.sha512(str(user_password).encode("latin1")).hexdigest()
                encrypted_pass = base64.b64encode(binascii.unhexlify(encrypted_pass)).decode()
                user_pass = user[0][2].replace("\n", "")
                if encrypted_pass == user_pass:
                    payload = {"email": user_email, "pass": user_password}
                    token = jwt.encode(payload, KEY, algorithm="HS256")
                    status = {"token": token}
            else:
                status = {"message": "No puede dejar campos vacios"}
        else:
            status = {"message": "El correo no esta registrado"}
        return status
