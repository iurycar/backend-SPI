
class Usuario:
    def __init__(
            self, id: int, 
            nome: str, 
            sobrenome: str | None,
            email: str, 
            password: str,
            perfil: str,
            admin: bool = False
            ):

        self.id = id
        self.nome = nome
        self.sobrenome = sobrenome
        self.email = email
        self.password = password
        self.perfil = perfil
        self.admin = admin

    def get_id(self) -> int | None:
        return self.id

    def get_name(self) -> str:
        return self.name
    
    def get_last_name(self) -> str | None:
        return self.last_name

    def get_full_name(self) -> str:
        if self.last_name:
            return f"{self.name} {self.last_name}"
        return self.name

    def get_email(self) -> str:
        return self.email

    def get_password(self) -> str:
        return self.password

    def get_role(self) -> str:
        return self.role

    def is_admin(self) -> bool:
        return self.admin