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

    def registrar_epi(self, nome: str, categoria: str, certificado: str, validade: str, estoque: int, quantidade_min: int, em_uso: int, id_epi: int | None) -> Epi | None:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO epis (nome, categoria, certificado, validade, estoque, quantidade_min, em_uso) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                    (nome, categoria, certificado, validade, estoque, quantidade_min, em_uso)
                )
                self.conn.commit()
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
            except Exception as e:
                print(f"Erro ao registrar EPI: {e}")
                self.conn.rollback()

        return None

    def deletar_epi(self, epi_id: int) -> bool:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "DELETE FROM epis WHERE id_epi = %s",
                    (epi_id,)
                )
                self.conn.commit()
                return cursor.rowcount > 0
            
            except Exception as e:
                print(f"Erro ao deletar EPI: {e}")
                self.conn.rollback()

    def atualizar_epi(self, epi_id: int, nome: str, categoria: str, certificado: str, validade: str, estoque: int, quantidade_min: int, em_uso: int) -> Epi | None:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "UPDATE epis SET nome = %s, categoria = %s, certificado = %s, validade = %s, estoque = %s, quantidade_min = %s, em_uso = %s WHERE id_epi = %s RETURNING *",
                    (nome, categoria, certificado, validade, estoque, quantidade_min, em_uso, epi_id)
                )
                self.conn.commit()
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
            except Exception as e:
                print(f"Erro ao atualizar EPI: {e}")
                self.conn.rollback()