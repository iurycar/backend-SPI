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

                id, nome, sobrenome, email, password, perfil, admin, unidade, telefone, ativo, acesso = resultado

                return Usuario(id, nome, sobrenome, email, password, perfil, admin, unidade, telefone, ativo, acesso)
            else:
                return None
        
    def criar_usuario(self, email: str, hashed_password: str, nome: str, sobrenome: str, perfil: str, unidade: str = None, telefone: str = None) -> Usuario:
        insert = "INSERT INTO usuarios (email, password, nome, sobrenome, perfil, unidade, telefone) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    insert,
                    (email, hashed_password, nome, sobrenome, perfil, unidade, telefone)
                )
                novo_id = cursor.fetchone()[0]

                self.conn.commit()

            return Usuario(novo_id, nome, sobrenome, email, hashed_password, perfil, False) 

        except Exception as e:
            print(f"Erro ao criar usuário: {e}")
            self.conn.rollback()
            return None

    def atualizar_acesso(self, usuario_id: int, acesso) -> None:
        update = "UPDATE usuarios SET acesso = %s WHERE id_usuario = %s"

        with self.conn.cursor() as cursor:
            cursor.execute(update, (acesso, usuario_id))
            self.conn.commit()

    def get_usuario_email_por_id(self, usuario_id: int) -> str | None:
        busca = "SELECT email FROM usuarios WHERE id_usuario = %s"

        with self.conn.cursor() as cursor:
            cursor.execute(busca, (usuario_id,))
            resultado = cursor.fetchone()

            if resultado:
                return resultado[0]

        return None