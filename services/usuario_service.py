from repository.usuario_repository import UsuarioRepository
import bcrypt

class UsuarioService:
    def __init__(self, user_repository: UsuarioRepository):
        self.user_repository = user_repository

    def login(self, email: str, password: str):
        usuario = self.user_repository.get_usuario_por_email(email)

        print(f"Usuario encontrado: {usuario.get_email() if usuario else 'Nenhum usuário encontrado'}")

        if usuario and self.check_password(password, usuario.get_password()):
            return usuario
        else:
            return None

    def check_password(self, password: str, hashed_password: str | bytes) -> bool:

        # Transformar a senha em hash com salt usando bcrypt
        # ==== !! RETIRAR DAQUI !! ====
        password = self.hashPassword(password)
        hashed_password = self.hashPassword(hashed_password)
        # ==== !! ATÉ AQUI !! ====

        password = password.encode('utf-8')

        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')

        return bcrypt.checkpw(password, hashed_password)

    # Função para gerar o hash da senha com salt usando bcrypt
    # Pode retirar
    def hashPassword(self, password: str) -> str:
        # Converte a senha de string para bytes
        password_bytes = password.encode('utf-8')
        
        # Gera um salt e faz o hash da senha
        salt_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))

        # Converte o hash de bytes para string antes de armazenar
        password_string = salt_password.decode('utf-8')
        #print(f"Hash gerado (string): {password_string}")

        return password_string