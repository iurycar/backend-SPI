from repository.responsabilidade_repository import ResponsabilidadeRepository

class ResponsabilidadeService:
    def __init__(self, connection, id_usuario: int | None = None, id_setor: int | None = None):
        self.responsabilidade_repository = ResponsabilidadeRepository(connection)
        self.id_usuario = id_usuario
        self.id_setor = id_setor

    def listar_responsabilidades_por_id_setor(self) -> dict | None:
        if self.id_setor is None:
            raise ValueError("O ID do setor não foi fornecido.")

        responsabilidades = self.responsabilidade_repository.get_responsabilidades_por_id_setor(self.id_setor)

        return responsabilidades if responsabilidades else None

    def listar_responsabilidades_por_id_usuario(self) -> dict | None:
        if self.id_usuario is None:
            raise ValueError("O ID do usuário não foi fornecido.")

        responsabilidades = self.responsabilidade_repository.get_responsabilidades_por_id_usuario(self.id_usuario)

        return responsabilidades if responsabilidades else None