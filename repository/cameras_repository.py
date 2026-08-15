from models.cameras import Camera

class CamerasRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_cameras(self) -> list[Camera] | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM cameras")
            cameras = cursor.fetchall()

            cameras_lista: list[Camera] = []

            if cameras:
                for camera in cameras:
                    cameras_lista.append(Camera(
                        id=camera[0],
                        ip=camera[1],
                        id_setor=camera[2]
                    ))

                return cameras_lista

            return None

    def get_camera_por_id(self, camera_id: int) -> Camera | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM cameras WHERE id_camera = %s", (camera_id,))
            camera = cursor.fetchone()

            if camera:
                return Camera(
                    id=camera[0],
                    ip=camera[1],
                    id_setor=camera[2]
                )

            return None

    def get_cameras_por_id_setor(self, setor_id: int) -> list[Camera] | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM cameras WHERE id_setor = %s", (setor_id,))
            cameras = cursor.fetchall()

            cameras_lista: list[Camera] = []

            if cameras:
                for camera in cameras:
                    cameras_lista.append(Camera(
                        id=camera[0],
                        ip=camera[1],
                        id_setor=camera[2]
                    ))

                return cameras_lista

            return None

    def registrar_camera(self, ip: str, id_setor: int) -> Camera | None:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO cameras (ip, id_setor) VALUES (%s, %s) RETURNING *",
                    (ip, id_setor)
                )
                self.conn.commit()
                camera = cursor.fetchone()

                if camera:
                    return Camera(
                        id=camera[0],
                        ip=camera[1],
                        id_setor=camera[2]
                    )

            except Exception as e:
                print(f"Erro ao registrar câmera: {e}")
                self.conn.rollback()

        return None

    def atualizar_camera(self, camera_id: int, ip: str, id_setor: int) -> Camera | None:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "UPDATE cameras SET ip = %s, id_setor = %s WHERE id_camera = %s RETURNING *",
                    (ip, id_setor, camera_id)
                )
                self.conn.commit()
                camera = cursor.fetchone()

                if camera:
                    return Camera(
                        id=camera[0],
                        ip=camera[1],
                        id_setor=camera[2]
                    )

            except Exception as e:
                print(f"Erro ao atualizar câmera: {e}")
                self.conn.rollback()

        return None

    def deletar_camera(self, camera_id: int) -> bool:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute("DELETE FROM cameras WHERE id_camera = %s", (camera_id,))
                self.conn.commit()

                return cursor.rowcount > 0
            
            except Exception as e:
                print(f"Erro ao deletar câmera: {e}")
                self.conn.rollback()

                return False