from repository.zonas_repository import ZonasRepository
from schemas.zona_dto import ZonaDTO
from flask import session

class ZonasService:
    def __init__(self, connection):
        self.zonas_repository = ZonasRepository(connection)

    def listar_zonas(self) -> list[dict]:
        zonas = self.zonas_repository.get_zonas()

        zonas_lista: list[dict] = []

        if not zonas:
            return zonas_lista

        for zona in zonas:
            zona_dict = {
                'id': zona.id,
                'nome': zona.nome,
                'x1': zona.x1,
                'y1': zona.y1,
                'x2': zona.x2,
                'y2': zona.y2,
                'id_camera': zona.id_camera
            }

            zonas_lista.append(zona_dict)

        return zonas_lista

    def obter_zona_por_id(self, zona_id: int) -> dict | None:
        zona = self.zonas_repository.get_zona_por_id(zona_id)

        if zona:
            return {
                'id': zona.id,
                'nome': zona.nome,
                'x1': zona.x1,
                'y1': zona.y1,
                'x2': zona.x2,
                'y2': zona.y2,
                'id_camera': zona.id_camera
            }

        return None

    def listar_zonas_por_id_camera(self, camera_id: int) -> list[dict]:
        zonas = self.zonas_repository.get_zonas_por_id_camera(camera_id)

        zonas_lista: list[dict] = []

        if zonas:
            for zona in zonas:
                zona_dict = {
                    'id': zona.id,
                    'nome': zona.nome,
                    'x1': zona.x1,
                    'y1': zona.y1,
                    'x2': zona.x2,
                    'y2': zona.y2,
                    'id_camera': zona.id_camera
                }
                zonas_lista.append(zona_dict)

        return zonas_lista

    def registrar_zona(self, data: dict) -> dict | None:
        try:
            zona_dto = ZonaDTO.from_dict(data)
        except ValueError as e:
            print(f"Erro ao criar ZonaDTO: {e}")
            return None

        zona = self.zonas_repository.registrar_zona(
            zona_dto.nome,
            zona_dto.x1,
            zona_dto.y1,
            zona_dto.x2,
            zona_dto.y2,
            zona_dto.id_camera
        )

        if zona:
            return {
                'id': zona.id,
                'nome': zona.nome,
                'x1': zona.x1,
                'y1': zona.y1,
                'x2': zona.x2,
                'y2': zona.y2,
                'id_camera': zona.id_camera
            }

        return None

    def atualizar_zona(self, zona_id: int, data: dict) -> dict | None:
        try:
            zona_dto = ZonaDTO.from_dict(data)
        except ValueError as e:
            print(f"Erro ao criar ZonaDTO: {e}")
            return None

        zona = self.zonas_repository.atualizar_zona(
            zona_id,
            zona_dto.nome,
            zona_dto.x1,
            zona_dto.y1,
            zona_dto.x2,
            zona_dto.y2,
            zona_dto.id_camera
        )

        if zona:
            return {
                'id': zona.id,
                'nome': zona.nome,
                'x1': zona.x1,
                'y1': zona.y1,
                'x2': zona.x2,
                'y2': zona.y2,
                'id_camera': zona.id_camera
            }

        return None

    def deletar_zona(self, zona_id: int) -> bool:
        sucesso = self.zonas_repository.deletar_zona(zona_id)
        return sucesso