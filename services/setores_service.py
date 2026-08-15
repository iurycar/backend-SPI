from repository.setores_repository import SetoresRepository
from flask import session

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
    