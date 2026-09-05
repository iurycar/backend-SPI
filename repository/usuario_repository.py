from models.usuarios import Usuario

class UsuarioRepository:
    def __init__(self, connection):
        self.conn = connection
    
    def get_usuario_por_email(self, email: str) -> Usuario | None:
        busca = "SELECT id_usuario, nome, sobrenome, email, senha, perfil, unidade, telefone, ativo, acesso FROM usuarios WHERE email = %s"

        with self.conn.cursor() as cursor:
            cursor.execute(busca, (email,))
            resultado = cursor.fetchone()

            if resultado:
                id_usuario, nome, sobrenome, email, senha, perfil, unidade, telefone, ativo, acesso = resultado

                return Usuario(id_usuario, nome, sobrenome, email, senha, perfil, unidade, telefone, ativo, acesso)
            else:
                return None
        
    def criar_usuario(self, email: str, hashed_password: str, nome: str, sobrenome: str, perfil: str, unidade: str = None, telefone: str = None) -> Usuario | None:
        insert = "INSERT INTO usuarios (email, senha, nome, sobrenome, perfil, unidade, telefone) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_usuario"

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    insert,
                    (email, hashed_password, nome, sobrenome, perfil, unidade, telefone)
                )
                novo_id = cursor.fetchone()[0]

                self.conn.commit()

            return Usuario(id=novo_id, nome=nome, sobrenome=sobrenome, email=email, password=hashed_password, perfil=perfil, unidade=unidade, telefone=telefone) 

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