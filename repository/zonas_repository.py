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
                        x=zona[2],
                        y=zona[3],
                        largura=zona[4],
                        altura=zona[5],
                        permitido=zona[6],
                        id_camera=zona[7]
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
                    x=zona[2],
                    y=zona[3],
                    largura=zona[4],
                    altura=zona[5],
                    permitido=zona[6],
                    id_camera=zona[7]
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
                        x=zona[2],
                        y=zona[3],
                        largura=zona[4],
                        altura=zona[5],
                        permitido=zona[6],
                        id_camera=zona[7]
                    ))

                return zonas_lista
            
            return None

    def registrar_zona(self, nome: str | None, id_camera: int, x: int = 0, y: int = 0, largura: int = 1920, altura: int = 1080, permitido: bool = True) -> Zona | None:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO zonas (nome, x, y, largura, altura, id_camera, permitido) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                    (nome, x, y, largura, altura, id_camera, permitido)
                )
                zona = cursor.fetchone()
                cursor.execute("COMMIT")

                if zona:
                    return Zona(
                        id=zona[0],
                        nome=zona[1],
                        x=zona[2],
                        y=zona[3],
                        largura=zona[4],
                        altura=zona[5],
                        permitido=zona[6],
                        id_camera=zona[7]
                    )
            except Exception as e:
                print(f"Erro ao registrar zona: {e}")
                self.conn.rollback()

        return None

    def atualizar_zona(self, zona_id: int, nome: str | None, id_camera: int, x: int = 0, y: int = 0, largura: int = 1920, altura: int = 1080, permitido: bool = True) -> Zona | None:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "UPDATE zonas SET nome = %s, x = %s, y = %s, largura = %s, altura = %s, id_camera = %s, permitido = %s WHERE id_zona = %s RETURNING *",
                    (nome, x, y, largura, altura, id_camera, permitido, zona_id)
                )
                self.conn.commit()
                zona = cursor.fetchone()

                if zona:
                    return Zona(
                        id=zona[0],
                        nome=zona[1],
                        x=zona[2],
                        y=zona[3],
                        largura=zona[4],
                        altura=zona[5],
                        permitido=zona[6],
                        id_camera=zona[7]
                    )
            except Exception as e:
                print(f"Erro ao atualizar zona: {e}")
                self.conn.rollback()
                            
        return None

    def deletar_zona(self, zona_id: int) -> bool:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute("DELETE FROM zonas WHERE id_zona = %s", (zona_id,))
                self.conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"Erro ao deletar zona: {e}")
                self.conn.rollback()
                return False