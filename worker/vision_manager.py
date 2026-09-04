from worker.vision_worker import VisionWorker

workers: dict[int, VisionWorker] = {}

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
    """Finaliza todos os workers de forma segura ao encerrar o servidor."""
    for camera_id, worker in workers.items():
        print(f"🛑 Encerrando worker da câmera {camera_id}...")
        worker.stop()

    workers.clear()