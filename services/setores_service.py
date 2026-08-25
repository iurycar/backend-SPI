from repository.setores_repository import SetoresRepository
from schemas.setor_dto import SetorDTO

class SetoresService:
    def __init__(self, connection):
        self.setores_repository = SetoresRepository(connection)

    def listar_setores(self) -> list[dict]:            
            setores_lista: list[dict] = []

            setores = self.setores_repository.get_setores()

            for setor in setores:
                setor_dict = {
                    'id': setor.id,
                    'nome': setor.nome,
                }

                setores_lista.append(setor_dict)

            return setores_lista

    def obter_setor_por_id(self, setor_id: int) -> dict | None:
        setor = self.setores_repository.get_setor_por_id(setor_id)

        if setor:
            return {
                'id': setor.id,
                'nome': setor.nome
            }

        return None

    def obter_setores_por_id_responsavel(self, usuario_id: int) -> list[dict]:
        setores = self.setores_repository.get_setores_por_id_responsavel(usuario_id)

        setores_lista: list[dict] = []

        if setores:
            for setor in setores:
                setor_dict = {
                    'id': setor.id,
                    'nome': setor.nome
                }
                setores_lista.append(setor_dict)

        return setores_lista

    def obter_setor_por_id_zona(self, zona_id: int) -> dict | None:
        setor = self.setores_repository.get_setor_por_id_zona(zona_id)

        if setor:
            return {
                'id': setor.id,
                'nome': setor.nome
            }

        return None

    def listar_setores_por_id_responsavel(self, usuario_id: int) -> list[dict]:
        setores = self.setores_repository.get_setores_por_id_responsavel(usuario_id)

        setores_lista: list[dict] = []

        if setores:
            for setor in setores:
                setor_dict = {
                    'id': setor.id,
                    'nome': setor.nome
                }
                setores_lista.append(setor_dict)

        return setores_lista

    def registrar_setor(self, data: dict) -> dict | None:
        try:
            setor_dto = SetorDTO.from_dict(data)
        except ValueError as e:
            print(f"Erro ao criar SetorDTO: {e}")
            return None

        setor = self.setores_repository.registrar_setor(
            setor_dto.nome
        )

        if setor:
            return {
                'id': setor.id,
                'nome': setor.nome
            }

        return None

    def atualizar_setor(self, setor_id: int, data: dict) -> dict | None:
        try:
            setor_dto = SetorDTO.from_dict(data)
        except ValueError as e:
            print(f"Erro ao criar SetorDTO: {e}")
            return None

        setor = self.setores_repository.atualizar_setor(
            setor_id,
            setor_dto.nome
        )

        if setor:
            return {
                'id': setor.id,
                'nome': setor.nome
            }

        return None

    def deletar_setor(self, setor_id: int) -> bool:
        sucesso = self.setores_repository.deletar_setor(setor_id)
        return sucesso