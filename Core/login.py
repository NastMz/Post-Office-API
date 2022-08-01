import base64
import binascii
import hashlib

from Database.Connection import DAO


class Login:
    def __init__(self):
        self.dao = DAO()

    def verify_crendentials(self, user_email, user_password):
        exist_mail = self.dao.get_email(user_email)
        status = "Fail"
        if exist_mail:
            user = self.dao.get_credential(user_email)
            if len(user) > 0:
                encrypted_pass = hashlib.sha512(str(user_password).encode("latin1")).hexdigest()
                encrypted_pass = base64.b64encode(binascii.unhexlify(encrypted_pass)).decode()
                user_pass = user[0][2].replace("\n", "")
                if encrypted_pass == user_pass:
                    status = "Credenciales correctas, ingresando a MassMail..."
            else:
                status = "No puede dejar el campo vacio."
        else:
            status = "Correo no existe, pruebe con otro correo."
        return status
