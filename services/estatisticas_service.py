from repository.estatisticas_repository import EstatisticasRepository
from schemas.intervalo_dto import IntervaloDTO

class EstatisticasService:
    def __init__(self, connection):
        self.estatisticas_repository = EstatisticasRepository(connection)

    def obter_estatisticas_conformidade(self, args) -> dict:
        intervalo_dto = IntervaloDTO.from_query_args(args)

        resultado = self.estatisticas_repository.get_estatisticas_conformidade(
            intervalo_dto.data_inicio, intervalo_dto.data_fim
        )

        return resultado

    def obter_estatisticas_por_setor(self, setor_id: int, args) -> dict:
        intervalo_dto = IntervaloDTO.from_query_args(args)

        estatisticas = self.estatisticas_repository.get_estatisticas_por_setor(setor_id, intervalo_dto.data_inicio, intervalo_dto.data_fim)

        return estatisticas