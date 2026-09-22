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

    def atualizar_usuario(self, 
                          usuario_id: int, 
                          nome: str, 
                          sobrenome: str,
                          email: str,
                          senha: str,
                          perfil: str,
                          unidade: str | None = None, 
                          telefone: str | None = None,
                          ativo: bool = True,
                          acesso: bool | None = None                      
    ) -> Usuario | None:
        try:
            with self.conn.cursor() as cursor:
                consulta = "UPDATE usuarios SET nome = %s, sobrenome = %s, email = %s, senha = %s, perfil = %s, unidade = %s, telefone = %s, ativo = %s, acesso = %s WHERE id_usuario = %s"
                cursor.execute(consulta, (nome, sobrenome, email, senha, perfil, unidade, telefone, ativo, acesso, usuario_id))
                self.conn.commit()

                return self.get_usuario_por_email(email)
            
        except Exception as e:
            print(f"Erro ao atualizar usuário: {e}")
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

    def listar_usuarios(self) -> list[Usuario]:
        with self.conn.cursor() as cursor:
            consulta = "SELECT id_usuario, nome, sobrenome, email, perfil, unidade, telefone, ativo FROM usuarios"
            cursor.execute(consulta)
            resultados = cursor.fetchall()

            usuarios = []
            for resultado in resultados:
                id_usuario, nome, sobrenome, email, perfil, unidade, telefone, ativo = resultado
                usuario = Usuario(id_usuario, nome, sobrenome, email, None, perfil, unidade, telefone, ativo)
                usuarios.append(usuario)

            return usuarios

    def listar_usuarios_ativos(self) -> list[Usuario]:
        with self.conn.cursor() as cursor:
            consulta = "SELECT id_usuario, nome, sobrenome, email, perfil, unidade, telefone, ativo FROM usuarios WHERE ativo = TRUE"
            cursor.execute(consulta)
            resultados = cursor.fetchall()

            usuarios_ativos = []
            for resultado in resultados:
                id_usuario, nome, sobrenome, email, perfil, unidade, telefone, ativo = resultado
                usuario = Usuario(id_usuario, nome, sobrenome, email, None, perfil, unidade, telefone, ativo)
                usuarios_ativos.append(usuario)

            return usuarios_ativos