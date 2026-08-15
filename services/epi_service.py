from repository.epi_repository import EpiRepository

class EpiService:
    def __init__(self, connection):
        self.epi_repository = EpiRepository(connection)

    def listar_epis(self) -> list[dict]:
        epis = self.epi_repository.get_epis()

        epis_lista: list[dict] = []

        if not epis:
            return []

        for epi in epis:
            epi_dict = {
                'id': epi.id,
                'nome': epi.nome,
                'categoria': epi.categoria,
                'validade': epi.validade,
                'estoque': epi.estoque,
                'quantidade_min': epi.quantidade_min,
                'em_uso': epi.em_uso
            }

            epis_lista.append(epi_dict)

        return epis_lista

    def obter_epi_por_id(self, epi_id: int) -> dict | None:
        epi = self.epi_repository.get_epi_por_id(epi_id)

        if epi:
            return {
                'id': epi.id,
                'nome': epi.nome,
                'categoria': epi.categoria,
                'validade': epi.validade,
                'estoque': epi.estoque,
                'quantidade_min': epi.quantidade_min,
                'em_uso': epi.em_uso
            }
        
        return None