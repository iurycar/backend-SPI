from repository.cameras_repository import CamerasRepository
from schemas.camera_dto import CameraDTO

class CamerasService:
    def __init__(self, connection):
        self.cameras_repository = CamerasRepository(connection)

    def listar_cameras(self) -> list[dict]:
        cameras = self.cameras_repository.get_cameras()

        cameras_lista: list[dict] = []

        for camera in cameras:
            camera_dict = {
                'id': camera.id,
                'ip': camera.ip,
                'id_setor': camera.id_setor
            }
            cameras_lista.append(camera_dict)

        return cameras_lista

    def obter_camera_por_id(self, camera_id: int) -> dict | None:
        camera = self.cameras_repository.get_camera_por_id(camera_id)

        if camera:
            return {
                'id': camera.id,
                'ip': camera.ip,
                'id_setor': camera.id_setor
            }

        return None

    def obter_cameras_por_id_setor(self, setor_id: int) -> list[dict]:
        cameras = self.cameras_repository.get_cameras_por_id_setor(setor_id)

        cameras_lista: list[dict] = []

        if cameras:
            for camera in cameras:
                camera_dict = {
                    'id': camera.id,
                    'ip': camera.ip,
                    'id_setor': camera.id_setor
                }
                cameras_lista.append(camera_dict)

        return cameras_lista

    def registrar_camera(self, data: dict) -> dict | None:
        try:
            camera_dto = CameraDTO.from_dict(data)
        except ValueError as e:
            print(f"Erro ao criar CameraDTO: {e}")
            return None
        
        camera = self.cameras_repository.registrar_camera(camera_dto.ip, camera_dto.id_setor)

        if camera:
            return {
                'id': camera.id,
                'ip': camera.ip,
                'id_setor': camera.id_setor
            }

        return None

    def atualizar_camera(self, camera_id: int, data: dict) -> dict | None:
        try:
            camera_dto = CameraDTO.from_dict(data)
        except ValueError as e:
            print(f"Erro ao criar CameraDTO: {e}")
            return None

        camera = self.cameras_repository.atualizar_camera(camera_id, camera_dto.ip, camera_dto.id_setor)

        if camera:
            return {
                'id': camera.id,
                'ip': camera.ip,
                'id_setor': camera.id_setor
            }

        return None

    def deletar_camera(self, camera_id: int) -> bool:
        successo = self.cameras_repository.deletar_camera(camera_id)
        return successo