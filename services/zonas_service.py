from repository.zonas_repository import ZonasRepository
from schemas.zona_dto import ZonaDTO
from extensions import redis_client
import json

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
                'x': zona.x,
                'y': zona.y,
                'largura': zona.largura,
                'altura': zona.altura,
                'permitido': zona.permitido,
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
                'x': zona.x,
                'y': zona.y,
                'largura': zona.largura,
                'altura': zona.altura,
                'permitido': zona.permitido,
                'id_camera': zona.id_camera
            }

        return None

    def listar_zonas_por_id_camera(self, camera_id: int) -> list[dict]:
        cache_chave = f"cache:zonas:camera:{camera_id}"

        # Busca os dados em cache no Redis
        dados_em_cache = redis_client.get(cache_chave)
        if dados_em_cache:
            try:
                zonas_lista = json.loads(dados_em_cache)
                return zonas_lista

            except json.JSONDecodeError:
                print("Erro ao decodificar os dados em cache. Obtendo do banco de dados.")

        # Caso não haja dados em cache ou ocorra um erro, busca do banco de dados
        zonas = self.zonas_repository.get_zonas_por_id_camera(camera_id)
        zonas_lista: list[dict] = []

        if zonas:
            for zona in zonas:
                zona_dict = {
                    'id': zona.id,
                    'nome': zona.nome,
                    'x': zona.x,
                    'y': zona.y,
                    'largura': zona.largura,
                    'altura': zona.altura,
                    'permitido': zona.permitido,
                    'id_camera': zona.id_camera
                }
                zonas_lista.append(zona_dict)

        # Salva os dados no cache Redis com um tempo de expiração de 1 hora (3600 segundos)
        redis_client.set(cache_chave, json.dumps(zonas_lista), ex=3600)

        return zonas_lista

    def obter_id_camera_por_zona(self, zona_id: int) -> int | None:
        zona = self.zonas_repository.get_zona_por_id(zona_id)
        if zona:
            return zona.id_camera
        return None

    def registrar_zona(self, data: dict) -> dict | None:
        try:
            zona_dto = ZonaDTO.from_dict(data)
        except ValueError as e:
            print(f"Erro ao criar ZonaDTO: {e}")
            return None

        zona = self.zonas_repository.registrar_zona(
            zona_dto.nome,
            zona_dto.id_camera,
            zona_dto.x,
            zona_dto.y,
            zona_dto.largura,
            zona_dto.altura,
            zona_dto.permitido
        )

        if zona:
            redis_client.delete(f"cache:zonas:camera:{zona.id_camera}")  # Invalida o cache para a câmera afetada

            return {
                'id': zona.id,
                'nome': zona.nome,
                'x': zona.x,
                'y': zona.y,
                'largura': zona.largura,
                'altura': zona.altura,
                'permitido': zona.permitido,
                'id_camera': zona.id_camera
            }

        return None

    def atualizar_zona(self, zona_id: int, data: dict) -> dict | None:
        try:
            zona_dto = ZonaDTO.from_dict(data)
        except ValueError as e:
            print(f"Erro ao criar ZonaDTO: {e}")
            return None

        print(f"Atualizando zona com ID {zona_id} usando dados: {data}")

        zona = self.zonas_repository.atualizar_zona(
            zona_id,
            zona_dto.nome,
            zona_dto.id_camera,
            zona_dto.x,
            zona_dto.y,
            zona_dto.largura,
            zona_dto.altura,
            zona_dto.permitido
        )

        if zona:
            redis_client.delete(f"cache:zonas:camera:{zona.id_camera}")  # Invalida o cache para a câmera afetada
            return {
                'id': zona.id,
                'nome': zona.nome,
                'x': zona.x,
                'y': zona.y,
                'largura': zona.largura,
                'altura': zona.altura,
                'permitido': zona.permitido,
                'id_camera': zona.id_camera
            }

        return None

    def deletar_zona(self, zona_id: int) -> bool:
        sucesso = self.zonas_repository.deletar_zona(zona_id)
        if sucesso:
            # Encontra a zona deletada para invalidar o cache
            zona = self.zonas_repository.obter_zona_por_id(zona_id)
            if zona:
                redis_client.delete(f"cache:zonas:camera:{zona.id_camera}")  # Invalida o cache para a câmera afetada
        return sucesso