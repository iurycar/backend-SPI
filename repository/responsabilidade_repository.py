from models.responsabilidade import Responsabilidade

class ResponsabilidadeRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_responsabilidades_por_id_setor(self, id_setor: int) -> list[Responsabilidade] | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM responsabilidades WHERE id_setor = %s", (id_setor,))
            responsabilidades = cursor.fetchall()

            # Transfere todos os resultados para uma lista de objetos Responsabilidade
            if responsabilidades:
                return [
                    Responsabilidade(
                        id=r[0],
                        id_usuario=r[1],
                        id_setor=r[2]
                    ) for r in responsabilidades
                ]
            else:
                return None

    def get_responsabilidades_por_id_usuario(self, id_usuario: int) -> list[Responsabilidade] | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM responsabilidades WHERE id_usuario = %s", (id_usuario,))
            responsabilidades = cursor.fetchall()

            if responsabilidades:
                return [
                    Responsabilidade(
                        id=r[0],
                        id_usuario=r[1],
                        id_setor=r[2]
                    ) for r in responsabilidades
                ]
            else:
                return None