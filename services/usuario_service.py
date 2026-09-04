from repository.usuario_repository import UsuarioRepository
from core.security import Security

from datetime import datetime

class UsuarioService:
    def __init__(self, connection):
        self.user_repository = UsuarioRepository(connection)
        self.security = Security()

    def login(self, email: str, password: str):
        usuario = self.user_repository.get_usuario_por_email(email)

        print(f"Usuario encontrado: {usuario.get_email() if usuario else 'Nenhum usuário encontrado'}")

        if usuario and self.security.check_password(password, usuario.get_password()):
            
            # Atualiza a data do último login do usuário
            usuario.set_acesso(datetime.now())
            self.user_repository.atualizar_acesso(usuario.get_id(), usuario.get_acesso())

            return usuario
        else:
            return None

    def signup(self, email: str, password: str, nome: str, sobrenome: str, perfil: str, unidade: str = None, telefone: str = None):
        usuario_existente = self.user_repository.get_usuario_por_email(email)

        if usuario_existente:
            return None

        hashed_password = self.security.hash_password(password)

        novo_usuario = self.user_repository.criar_usuario(email, hashed_password, nome, sobrenome, perfil, unidade, telefone)

        return novo_usuario

    def obter_email_usuario_por_id(self, usuario_id: int) -> str | None:
        email = self.user_repository.get_usuario_email_por_id(usuario_id)

        if email:
            return email

        return None