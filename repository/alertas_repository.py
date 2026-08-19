from models.alertas import Alerta

class AlertasRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_alertas(self) -> list[Alerta] | None:
        with self.conn.cursor() as cursor:
            query = "SELECT a.*, m.id_zona, m.id_camera, m.id_epi FROM alertas a JOIN monitorar m ON m.id_monitorar = a.id_monitorar;"
            cursor.execute(query)
            alertas = cursor.fetchall()

            alertas_lista: list[Alerta] = []

            if alertas:
                for alerta in alertas:
                    alertas_lista.append(Alerta(
                        id=alerta[0],
                        resolvido=alerta[1],
                        data=alerta[2].strftime("%Y-%m-%d %H:%M:%S"),
                        id_monitorar=alerta[3],
                        id_usuario=alerta[4],
                        evento=alerta[5],
                        id_zona=alerta[6],
                        id_camera=alerta[8],
                        id_epi=alerta[7]
                    ))
            return alertas_lista

        return None

    def get_alertas_por_id_camera(self, id_camera: int) -> list[Alerta] | None:
        with self.conn.cursor() as cursor:
            query = "SELECT a.*, m.id_zona, m.id_camera, m.id_epi FROM alertas a JOIN monitorar m ON m.id_monitorar = a.id_monitorar WHERE m.id_camera = %s;"
            cursor.execute(query, (id_camera,))
            alertas = cursor.fetchall()

            alertas_lista: list[Alerta] = []

            if alertas:
                for alerta in alertas:
                    alertas_lista.append(Alerta(
                        id=alerta[0],
                        resolvido=alerta[1],
                        data=alerta[2].strftime("%Y-%m-%d %H:%M:%S"),
                        id_monitorar=alerta[3],
                        id_usuario=alerta[4],
                        evento=alerta[5],
                        id_zona=alerta[6],
                        id_camera=alerta[8],
                        id_epi=alerta[7]
                    ))

            return alertas_lista if alertas_lista else None

    def get_alertas_por_id_zona(self, id_zona: int) -> list[Alerta] | None:
        with self.conn.cursor() as cursor:
            query = "SELECT a.*, m.id_zona, m.id_camera, m.id_epi FROM alertas a JOIN monitorar m ON m.id_monitorar = a.id_monitorar WHERE m.id_zona = %s;"
            cursor.execute(query, (id_zona,))
            alertas = cursor.fetchall()

            alertas_lista: list[Alerta] = []

            if alertas:
                for alerta in alertas:
                    alertas_lista.append(Alerta(
                        id=alerta[0],
                        resolvido=alerta[1],
                        data=alerta[2].strftime("%Y-%m-%d %H:%M:%S"),
                        id_monitorar=alerta[3],
                        id_usuario=alerta[4],
                        evento=alerta[5],
                        id_zona=alerta[6],
                        id_camera=alerta[8],
                        id_epi=alerta[7]
                    ))

            return alertas_lista if alertas_lista else None

    def get_alerta_por_id(self, id_alerta: int) -> Alerta | None:
        with self.conn.cursor() as cursor:
            query = "SELECT a.*, m.id_zona, m.id_camera, m.id_epi FROM alertas a JOIN monitorar m ON m.id_monitorar = a.id_monitorar WHERE a.id_alerta = %s;"
            cursor.execute(query, (id_alerta,))
            alerta = cursor.fetchone()

            if alerta:
                return Alerta(
                    id=alerta[0],
                    resolvido=alerta[1],
                    data=alerta[2].strftime("%Y-%m-%d %H:%M:%S"),
                    id_monitorar=alerta[3],
                    id_usuario=alerta[4],
                    evento=alerta[5],
                    id_zona=alerta[6],
                    id_camera=alerta[8],
                    id_epi=alerta[7]
                )

        return None

    def marcar_alerta_resolvido(self, id_alerta: int) -> bool:
        with self.conn.cursor() as cursor:
            query = "UPDATE alertas SET resolvido = TRUE WHERE id_alerta = %s;"
            cursor.execute(query, (id_alerta,))
            self.conn.commit()
            return cursor.rowcount > 0

    def criar_alerta(self, id_monitorar: int, id_usuario: int | None, evento: str) -> bool:
        with self.conn.cursor() as cursor:
            query = "INSERT INTO alertas (resolvido, data, id_monitorar, id_usuario, evento) VALUES (FALSE, NOW(), %s, %s, %s);"
            cursor.execute(query, (id_monitorar, id_usuario, evento))
            self.conn.commit()
            return cursor.rowcount > 0