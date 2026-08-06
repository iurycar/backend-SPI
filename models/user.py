
class User:
    def __init__(self, id: int | None, username: str, email: str, password: str):
        self.id = id
        self.username = username
        self.email = email
        self.password = password