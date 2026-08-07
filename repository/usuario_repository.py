from models.usuarios import Usuario

usuarios_teste = [
    Usuario(1, "Alice", "alice@example.com", "password123", "user", False), 
    Usuario(2, "Bob", "bob@example.com", "password456", "admin", True),
    Usuario(3, "Administrador", "admin@visaoepi.com", "123456", "admin", True),
    ]

class UsuarioRepository:
    def __init__(self):
        self.usuarios = usuarios_teste

    def get_usuario_por_email(self, email: str) -> Usuario | None:
        for usuario in self.usuarios:
            if usuario.get_email() == email:
                return usuario

        return None