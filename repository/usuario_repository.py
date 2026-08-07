from models.usuarios import Usuario

usuarios_teste = [
    Usuario(1, "Alice", "alice@example.com", "$2b$12$6zF3X0GDZgeFpL7NuGKt/esQFh6we93ZqbPwEn8q76r4ZSHc4l9Zi", "user", False), 
    Usuario(2, "Bob", "bob@example.com", "$2b$12$6zF3X0GDZgeFpL7NuGKt/esQFh6we93ZqbPwEn8q76r4ZSHc4l9Zi", "admin", True),
    Usuario(3, "Administrador", "admin@visaoepi.com", "$2b$12$6zF3X0GDZgeFpL7NuGKt/esQFh6we93ZqbPwEn8q76r4ZSHc4l9Zi", "admin", True),
    ]

class UsuarioRepository:
    def __init__(self):
        self.usuarios = usuarios_teste

    def get_usuario_por_email(self, email: str) -> Usuario | None:
        for usuario in self.usuarios:
            if usuario.get_email() == email:
                return usuario

        return None