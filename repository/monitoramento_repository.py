from models.monitoramento import Monitoramento

class MonitoramentoRepository:
    def __init__(self, connection):
        self.connection = connection

    def get_monitoramentos_por_id_camera(self, camera_id) -> list[Monitoramento] | None:
        """
        Retorna uma lista de objetos Monitoramento para uma câmera específica.
        """

        with self.connection.cursor() as cursor:
            query = """
                SELECT id_monitorar, id_zona, id_epi
                FROM monitorar
                WHERE id_camera = %s
            """

            cursor.execute(query, (camera_id,))
            monitoramento = cursor.fetchall()

            zonas_monitoramento: list[Monitoramento] = []

            if monitoramento:
                for zona in monitoramento:
                    zonas_monitoramento.append(Monitoramento(
                        id=zona[0],
                        id_camera=camera_id,
                        id_zona=zona[1],
                        id_epi=zona[2]
                    ))

                return zonas_monitoramento

            return None