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
