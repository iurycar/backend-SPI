from services.cameras_service import CamerasService
from worker.vision_worker import VisionWorker
from connection.conn import Connection

workers: dict[int, VisionWorker] = {}

def iniciar_todos_os_workers():
    """
        Lista todas as câmeras cadastradas e inicia um VisionWorker para cada uma delas.
    """

    connection = Connection().get_connection()
    cameras_service = CamerasService(connection)

    cameras = cameras_service.listar_cameras()

    if not cameras:
        print("⚠️ Nenhuma câmera cadastrada no banco de dados.")
        return

    for camera in cameras:
        camera_id = camera.get('id') if isinstance(camera, dict) else getattr(camera, 'id', None)

        if camera_id is None:
            cam_id = camera.get('id_camera') if isinstance(camera, dict) else getattr(camera, 'id_camera', None)

        if camera_id is not None and camera_id not in workers:
            worker = VisionWorker(camera_id=camera_id)
            worker.start()
            workers[camera_id] = worker
            print(f"🎥 Worker para câmera {camera_id} iniciado.")
        

def iniciar_vision_workers(camera_ids: list[int]):
    """
    Inicia os VisionWorkers para as câmeras especificadas.
    """
    for camera_id in camera_ids:
        if camera_id not in workers:
            worker = VisionWorker(camera_id=camera_id)
            worker.start()
            workers[camera_id] = worker
            print(f"🎥 Worker para câmera {camera_id} iniciado.")


def parar_vision_workers():
    """Finaliza todos os workers de forma segura ao encerrar a aplicação."""
    for camera_id, worker in list(workers.items()):
        print(f"🛑 Encerrando worker da câmera {camera_id}...")
        worker.stop()

    workers.clear()


def get_camera_status(camera_id: int) -> dict:
    worker = workers.get(camera_id)

    if not worker:
        return 'Inativo'

    return 'Ativo' if worker.is_online() else 'Desconectado'