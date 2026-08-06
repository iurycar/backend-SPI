
class User:
    def __init__(
            self, id: int | None, 
            username: str, 
            email: str, 
            password: str,
            role: str,
            admin: bool = False
            ):

        self.id = id
        self.username = username
        self.email = email
        self.password = password
        self.role = role
        self.admin = admin