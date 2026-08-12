from models.usuarios import Usuario

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
                print(f"Resultado da consulta para email '{email}': {resultado}")

                id, nome, sobrenome, email, password, perfil, admin, unidade, telefone, ativo = resultado

                return Usuario(id, nome, sobrenome, email, password, perfil, admin, unidade, telefone, ativo)
            else:
                return None
        
    def criar_usuario(self, email: str, hashed_password: str, nome: str, sobrenome: str, perfil: str, unidade: str = None, telefone: str = None) -> Usuario:
        insert = "INSERT INTO usuarios (email, password, nome, sobrenome, perfil, unidade, telefone) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"

        with self.conn.cursor() as cursor:
            cursor.execute(
                insert,
                (email, hashed_password, nome, sobrenome, perfil, unidade, telefone)
            )
            novo_id = cursor.fetchone()[0]

            self.conn.commit()

        return Usuario(novo_id, nome, sobrenome, email, hashed_password, perfil, False) 