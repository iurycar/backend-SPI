from repository.usuario_repository import UsuarioRepository
import core.security as security

class UsuarioService:
    def __init__(self, connection):
        self.user_repository = UsuarioRepository(connection)

    def login(self, email: str, password: str):
        usuario = self.user_repository.get_usuario_por_email(email)

        print(f"Usuario encontrado: {usuario.get_email() if usuario else 'Nenhum usuário encontrado'}")

        if usuario and security.check_password(password, usuario.get_password()):
            return usuario
        else:
            return None

    def signup(self, email: str, password: str, nome: str, sobrenome: str, perfil: str, unidade: str = None, telefone: str = None):
        usuario_existente = self.user_repository.get_usuario_por_email(email)

        if usuario_existente:
            return None

        hashed_password = security.hash_password(password)

        novo_usuario = self.user_repository.criar_usuario(email, hashed_password, nome, sobrenome, perfil, unidade, telefone)

        return novo_usuario