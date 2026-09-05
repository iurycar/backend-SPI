from worker.vision_worker import VisionWorker

workers: dict[int, VisionWorker] = {}

def iniciar_todos_os_workers(cameras_id: list[int]):
    """
        Lista todas as câmeras cadastradas e inicia um VisionWorker para cada uma delas.
    """
    for camera_id in cameras_id:
        if camera_id not in workers:
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

def notificar_atualizacao_zonas(camera_id: int):
    """
    Notifica o worker da câmera especificada para recarregar as zonas de monitoramento.
    """
    worker = workers.get(camera_id)

    if worker:
        worker.reload_zones()

def notificar_desligamento_camera(camera_id: int):
    """
    Notifica o worker da câmera especificada para desligar.
    """
    worker = workers.get(camera_id)

    if worker:
        worker.stop()
        del workers[camera_id]
        print(f"🛑 Worker para a câmera {camera_id} foi desligado.")