
class EpiService:
    def __init__(self, epi_repository):
        self.epi_repository = epi_repository

    def listar_epis(self) -> list[dict]:
        epis = self.epi_repository.listar_epis()

        epis_validos: list[dict] = []
        for epi in epis:
            if epi['estoque'] >= 0:
                epis_validos.append(epi)

        return epis_validos