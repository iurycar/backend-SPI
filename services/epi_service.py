from repository.epi_repository import EpiRepository

class EpiService:
    def __init__(self, connection):
        self.epi_repository = EpiRepository(connection)

    def listar_epis(self) -> list[dict]:
        epis = self.epi_repository.listar_epis()

        epis_validos: list[dict] = []
        for epi in epis:
            if epi['estoque'] >= 0:
                epis_validos.append(epi)

        return epis_validos