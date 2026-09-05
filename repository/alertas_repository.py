from models.alertas import Alerta

class AlertasRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_alertas(self) -> list[Alerta]:
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
                        data_hora=alerta[2].strftime("%Y-%m-%d %H:%M:%S"),
                        id_monitorar=alerta[3],
                        id_usuario=alerta[4],
                        evento=alerta[5],
                        severidade=alerta[6],
                        id_zona=alerta[7],
                        id_camera=alerta[8],
                        id_epi=alerta[9]
                    ))

            return alertas_lista

    def get_alertas_por_id_camera(self, id_camera: int) -> list[Alerta]:
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
                        data_hora=alerta[2].strftime("%Y-%m-%d %H:%M:%S"),
                        id_monitorar=alerta[3],
                        id_usuario=alerta[4],
                        evento=alerta[5],
                        severidade=alerta[6],
                        id_zona=alerta[7],
                        id_camera=alerta[8],
                        id_epi=alerta[9]
                    ))

            return alertas_lista

    def get_alertas_por_id_zona(self, id_zona: int) -> list[Alerta]:
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
                        data_hora=alerta[2].strftime("%Y-%m-%d %H:%M:%S"),
                        id_monitorar=alerta[3],
                        id_usuario=alerta[4],
                        evento=alerta[5],
                        severidade=alerta[6],
                        id_zona=alerta[7],
                        id_camera=alerta[8],
                        id_epi=alerta[9]
                    ))

            return alertas_lista

    def get_alerta_por_id(self, id_alerta: int) -> Alerta | None:
        with self.conn.cursor() as cursor:
            query = "SELECT a.*, m.id_zona, m.id_camera, m.id_epi FROM alertas a JOIN monitorar m ON m.id_monitorar = a.id_monitorar WHERE a.id_alerta = %s;"
            cursor.execute(query, (id_alerta,))
            alerta = cursor.fetchone()

            if alerta:
                return Alerta(
                    id=alerta[0],
                    resolvido=alerta[1],
                    data_hora=alerta[2].strftime("%Y-%m-%d %H:%M:%S"),
                    id_monitorar=alerta[3],
                    id_usuario=alerta[4],
                    evento=alerta[5],
                    severidade=alerta[6],
                    id_zona=alerta[7],
                    id_camera=alerta[8],
                    id_epi=alerta[9]
                )
            else:
                return None
            
    def get_alertas_por_id_usuario(self, id_usuario: int) -> list[Alerta]:
        with self.conn.cursor() as cursor:
            query = "SELECT a.*, m.id_zona, m.id_camera, m.id_epi FROM alertas a JOIN monitorar m ON m.id_monitorar = a.id_monitorar WHERE a.id_usuario = %s;"
            cursor.execute(query, (id_usuario,))
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
                        severidade=alerta[6],
                        id_zona=alerta[7],
                        id_camera=alerta[8],
                        id_epi=alerta[9]
                    ))

            return alertas_lista

    def marcar_alerta_resolvido(self, id_alerta: int) -> bool:
        with self.conn.cursor() as cursor:
            query = "UPDATE alertas SET resolvido = TRUE WHERE id_alerta = %s;"
            cursor.execute(query, (id_alerta,))
            self.conn.commit()

            return cursor.rowcount > 0

    def criar_alerta(self, id_monitorar: int, id_usuario: int | None, evento: str, severidade: int = 1) -> bool:
        with self.conn.cursor() as cursor:
            query = "INSERT INTO alertas (resolvido, data_hora, id_monitorar, id_usuario, evento, severidade) VALUES (FALSE, NOW(), %s, %s, %s, %s);"
            cursor.execute(query, (id_monitorar, id_usuario, evento, severidade))
            self.conn.commit()

            return cursor.rowcount > 0

    def deletar_alerta(self, id_alerta: int) -> bool:
        with self.conn.cursor() as cursor:
            query = "DELETE FROM alertas WHERE id_alerta = %s;"
            cursor.execute(query, (id_alerta,))
            self.conn.commit()

            return cursor.rowcount > 0

    def get_contangem_por_tipo_epi(self) -> list[dict]:
        with self.conn.cursor() as cursor:
            query = """
                SELECT COALESCE(e.categoria, 'Sem Categoria') AS categoria, COUNT(*) AS total
                FROM alertas a
                JOIN monitorar m ON m.id_monitorar = a.id_monitorar
                LEFT JOIN epis e ON e.id_epi = m.id_epi
                GROUP BY COALESCE(e.categoria, 'Sem Categoria')
                ORDER BY total DESC;
            """

            cursor.execute(query)
            resultados = cursor.fetchall()

            valores: list[dict] = []

            for categoria, total in resultados:
                valores.append({
                    "categoria": categoria,
                    "total": total
                })

            return valores

    def get_contagem_por_dia(self, desde) -> list[dict]:
        with self.conn.cursor() as cursor:
            query = """
                SELECT DATE(a.data_hora) AS dia, COUNT(*) AS total
                FROM alertas a
                WHERE a.data_hora >= %s
                GROUP BY DATE(a.data_hora)
                ORDER BY dia ASC;
            """

            cursor.execute(query, (desde,))
            resultados = cursor.fetchall()

            valores: list[dict] = []

            for dia, total in resultados:
                valores.append({
                    "dia": dia.strftime("%Y-%m-%d"),
                    "total": total
                })

            return valores