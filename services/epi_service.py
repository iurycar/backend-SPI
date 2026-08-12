from repository.epi_repository import EpiRepository

class EpiService:
    def __init__(self, connection):
        self.epi_repository = EpiRepository(connection)

    def listar_epis(self) -> list[dict]:
        epis = self.epi_repository.get_epis()

        epis_lista: list[dict] = []
        
        for epi in epis:
            epi_dict = {
                'id': epi[0],
                'nome': epi[1],
                'categoria': epi[2],
                'validade': epi[3],
                'estoque': epi[4]
            }

            epis_lista.append(epi_dict)

        return epis_lista