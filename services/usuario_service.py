from repository.usuario_repository import UsuarioRepository
from schemas.usuario_dto import UsuarioDTO
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

    def obter_status_ativo(self, email: str) -> bool:
        usuario = self.user_repository.get_usuario_por_email(email)

        if usuario and usuario.is_ativo:
            return usuario.is_ativo

        return False

    def listar_usuarios(self) -> list[dict]:
        usuarios = self.user_repository.listar_usuarios()

        lista_usuarios = []

        if usuarios:
            for usuario in usuarios:
                lista_usuarios.append({
                    'id': usuario.get_id(),
                    'nome': usuario.get_nome(),
                    'sobrenome': usuario.get_sobrenome(),
                    'email': usuario.get_email(),
                    'perfil': usuario.get_perfil(),
                    'unidade': usuario.get_unidade(),
                    'telefone': usuario.get_telefone(),
                    'admin': usuario.is_admin,
                    'ativo': usuario.is_ativo
                })

        return lista_usuarios

    def atualizar_usuario(self, data) -> dict:
        try:
            usuario_dto = UsuarioDTO.from_dict(data)
        except Exception as e:
            print(f"Erro ao criar DTO: {e}")
            return None
        
        if not usuario_dto.id:
            return None

        usuario_atualizado = self.user_repository.atualizar_usuario(
            usuario_dto.id,
            usuario_dto.nome,
            usuario_dto.sobrenome,
            usuario_dto.email,
            usuario_dto.senha,
            usuario_dto.perfil,
            usuario_dto.unidade,
            usuario_dto.telefone,
            usuario_dto.ativo
        )

        return usuario_atualizado

    def deletar_usuario(self, usuario_id: int) -> bool:
        sucesso = self.user_repository.deletar_usuario(usuario_id)
        if sucesso:
            return True
        return False

    def listar_usuarios_ativos(self) -> list[dict]:
        usuarios = self.user_repository.listar_usuarios_ativos()

        lista_usuarios = []

        if usuarios:
            for usuario in usuarios:
                lista_usuarios.append({
                    'id': usuario.get_id(),
                    'nome': usuario.get_nome(),
                    'sobrenome': usuario.get_sobrenome(),
                    'email': usuario.get_email(),
                    'perfil': usuario.get_perfil(),
                    'unidade': usuario.get_unidade(),
                    'telefone': usuario.get_telefone(),
                    'admin': usuario.is_admin,
                    'ativo': usuario.is_ativo
                })

        return lista_usuarios