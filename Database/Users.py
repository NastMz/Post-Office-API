from Database.Connection import DAO


class Users:
    def __init__(self):
        self.dao = DAO()

    def get_users(self):
        users = self.dao.get_users()
        users_dict = []
        for user in users:
            users_dict.append({"name": user[0], "email": user[1]})
        return users_dict


u = Users()
u.get_users()