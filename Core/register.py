import base64
import binascii
import hashlib
import re

from Database.Connection import DAO

class Register:
    def __init__(self):
        self.dao = DAO()

    def validate_email_form(self, new_email):
        message = []
        validate_email = re.match('\w+@massmail.site', new_email, re.I)
        if not validate_email:
            message.append('Esta dirección de correo no es valida')
        if len(message) > 0:
            return False, message
        else:
            return True, message

    def validate_user_info(self, new_email,new_password, new_fname):
        message = []
        validate_email = re.match('\w+', new_email, re.I)
        validate_pass = re.match('\w+', new_password, re.I)
        validate_fname = re.match('\w+', new_fname, re.I)

        if not validate_email:
            message.append('Ingrese un correo')
        else:
            status, message = self.validate_email_form(new_email)
        if not validate_pass:
            message.append('Ingrese una contraseña')
        if not validate_fname:
            message.append('Ingrese nombre completo')
        if len(message) > 0:
            return False, message
        else:
            return True, message

    def register_user(self, user_email, user_password, user_fname):
        exist_mail = self.dao.get_email(user_email)
        status, message = self.validate_user_info(user_email, user_password, user_fname)
        if status:
            if not exist_mail:
                self.dao.set_user(user_email, user_password, user_fname)
                message.append('Correo registrado con éxito.')
            else:
                message.append('El correo ya se encuentra registrado.')
        return message

