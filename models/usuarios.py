
class Usuario:
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

    def get_id(self) -> int | None:
        return self.id

    def get_username(self) -> str:
        return self.username

    def get_email(self) -> str:
        return self.email

    def get_password(self) -> str:
        return self.password

    def get_role(self) -> str:
        return self.role

    def is_admin(self) -> bool:
        return self.admin