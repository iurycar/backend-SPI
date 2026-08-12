from models.usuarios import Usuario

usuarios_teste = [
    Usuario(1, "Alice", "alice@example.com", "$2b$12$6zF3X0GDZgeFpL7NuGKt/esQFh6we93ZqbPwEn8q76r4ZSHc4l9Zi", "user", False), 
    Usuario(2, "Bob", "bob@example.com", "$2b$12$6zF3X0GDZgeFpL7NuGKt/esQFh6we93ZqbPwEn8q76r4ZSHc4l9Zi", "admin", True),
    Usuario(3, "Administrador", "admin@visaoepi.com", "$2b$12$6zF3X0GDZgeFpL7NuGKt/esQFh6we93ZqbPwEn8q76r4ZSHc4l9Zi", "admin", True),
    ]

class UsuarioRepository:
    def __init__(self, connection):
        self.conn = connection
    
    def get_usuario_por_email(self, email: str) -> Usuario | None:
        busca = "SELECT * FROM usuarios WHERE email = %s"

        with self.conn.cursor() as cursor:
            cursor.execute(busca, (email,))
            resultado = cursor.fetchone()

            print(f"Resultado da consulta para email '{email}': {resultado}")

            if resultado:
                id, nome, sobrenome, email, password, perfil, admin = resultado
                return Usuario(id, nome, sobrenome, email, password, perfil, admin)
            else:
                return None
        
    def criar_usuario(self, email: str, hashed_password: str, nome: str, sobrenome: str, perfil: str, unidade: str = None, telefone: str = None) -> Usuario:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (email, password, nome, sobrenome, perfil, unidade, telefone) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (email, hashed_password, nome, sobrenome, perfil, unidade, telefone)
            )
            novo_id = cursor.fetchone()[0]
        return Usuario(novo_id, nome, sobrenome, email, hashed_password, perfil, False) 