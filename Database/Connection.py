import mysql.connector
from mysql.connector import Error

from Config.Config import HOST, DB_PORT, DB_CHARSET, DB_NAME, DB_PASS, DB_USER


class DAO:
    def __init__(self):
        try:
            self.connection = mysql.connector.connect(
                host=HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASS,
                db=DB_NAME,
                charset=DB_CHARSET,
            )
        except Error as ex:
            print("Error on try connect: {0}".format(ex))

    def get_user(self, user_email):
        if self.connection.is_connected():
            try:
                cursor = self.connection.cursor()
                cursor.execute(f"SELECT fullname FROM virtual_Users WHERE email='{user_email}'")
                result = cursor.fetchall()
                return result
            except Error as ex:
                print("Error on try connect: {0}".format(ex))

    def get_email(self, user_email):
        if self.connection.is_connected():
            try:
                cursor = self.connection.cursor()
                cursor.execute(f"SELECT email FROM virtual_Users WHERE email='{user_email}'")
                result = cursor.fetchall()
                return result
            except Error as ex:
                print("Error on try connect: {0}".format(ex))

    def get_credential(self, user_email):
        if self.connection.is_connected():
            try:
                cursor = self.connection.cursor()
                cursor.execute(f"SELECT * FROM virtual_Users WHERE email='{user_email}'")
                result = cursor.fetchall()
                return result
            except Error as ex:
                print("Error on try connect: {0}".format(ex))

    def set_user(self, new_email, new_pass, user_fname):
        if self.connection.is_connected():
            try:
                cursor = self.connection.cursor()
                cursor.execute(f"INSERT INTO virtual_Users (domain_name,email,password,fullname,department) VALUES ('massmail.site','{new_email}',TO_BASE64(UNHEX(SHA2('{new_pass}', 512))),'{user_fname}','User')")
                self.connection.commit()
                result = cursor.fetchall()
                return result
            except Error as ex:
                print("Error on try connect: {0}".format(ex))