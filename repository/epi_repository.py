from models.epis import Epi

class EpiRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_epis(self) -> list[Epi] | None:

        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM epis")
            epis = cursor.fetchall()

            epis_lista: list[Epi] = []

            # Transfere todos os resultados para uma lista de objetos Epi
            if epis:
                for epi in epis:

                    epis_lista.append(Epi(
                        id=epi[0],
                        nome=epi[1],
                        categoria=epi[2],
                        certificado=epi[3],
                        validade=epi[4],
                        estoque=epi[5],
                        quantidade_min=epi[6],
                        em_uso=epi[7]
                    ))

                return epis_lista
            
            return None

    def get_epi_por_id(self, epi_id: int) -> Epi | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM epis WHERE id_epi = %s", (epi_id,))
            epi = cursor.fetchone()

            if epi:
                return Epi(
                    id=epi[0],
                    nome=epi[1],
                    categoria=epi[2],
                    certificado=epi[3],
                    validade=epi[4],
                    estoque=epi[5],
                    quantidade_min=epi[6],
                    em_uso=epi[7]
                )
            else:
                return None