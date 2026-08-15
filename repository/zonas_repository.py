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