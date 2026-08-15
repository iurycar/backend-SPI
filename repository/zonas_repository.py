from models.zonas import Zona

class ZonasRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_zonas(self) -> list[Zona] | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM zonas")
            zonas = cursor.fetchall()

            zonas_lista: list[Zona] = []

            # Transfere todos os resultados para uma lista de objetos Zona
            if zonas:
                for zona in zonas:
                    zonas_lista.append(Zona(
                        id=zona[0],
                        nome=zona[1],
                        x1=zona[2],
                        y1=zona[3],
                        x2=zona[4],
                        y2=zona[5],
                        id_camera=zona[6]
                    ))

                return zonas_lista
            
            return None

    def get_zona_por_id(self, zona_id: int) -> Zona | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM zonas WHERE id_zona = %s", (zona_id,))
            zona = cursor.fetchone()

            if zona:
                return Zona(
                    id=zona[0],
                    nome=zona[1],
                    id_camera=zona[6],
                    x1=zona[2],
                    y1=zona[3],
                    x2=zona[4],
                    y2=zona[5]
                )
            else:
                return None

    def get_zonas_por_id_camera(self, camera_id: int) -> list[Zona] | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM zonas WHERE id_camera = %s", (camera_id,))
            zonas = cursor.fetchall()

            zonas_lista: list[Zona] = []

            # Transfere todos os resultados para uma lista de objetos Zona
            if zonas:
                for zona in zonas:
                    zonas_lista.append(Zona(
                        id=zona[0],
                        nome=zona[1],
                        id_camera=zona[6],
                        x1=zona[2],
                        y1=zona[3],
                        x2=zona[4],
                        y2=zona[5]
                    ))

                return zonas_lista
            
            return None

    def registrar_zona(self, nome: str | None, id_camera: int, x1: int = 0, y1: int = 0, x2: int = 1920, y2: int = 1080) -> Zona | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO zonas (nome, x1, y1, x2, y2, id_camera) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
                (nome, x1, y1, x2, y2, id_camera)
            )
            zona = cursor.fetchone()

            if zona:
                return Zona(
                    id=zona[0],
                    nome=zona[1],
                    id_camera=zona[6],
                    x1=zona[2],
                    y1=zona[3],
                    x2=zona[4],
                    y2=zona[5]
                )
            else:
                return None

    def atualizar_zona(self, zona_id: int, nome: str | None, id_camera: int, x1: int = 0, y1: int = 0, x2: int = 1920, y2: int = 1080) -> Zona | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "UPDATE zonas SET nome = %s, x1 = %s, y1 = %s, x2 = %s, y2 = %s, id_camera = %s WHERE id_zona = %s RETURNING *",
                (nome, x1, y1, x2, y2, id_camera, zona_id)
            )
            zona = cursor.fetchone()

            if zona:
                return Zona(
                    id=zona[0],
                    nome=zona[1],
                    id_camera=zona[6],
                    x1=zona[2],
                    y1=zona[3],
                    x2=zona[4],
                    y2=zona[5]
                )
            else:
                return None

    def deletar_zona(self, zona_id: int) -> bool:
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM zonas WHERE id_zona = %s", (zona_id,))
            return cursor.rowcount > 0