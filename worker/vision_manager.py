from worker.vision_worker import VisionWorker

workers: dict[int, VisionWorker] = {}

def iniciar_vision_workers(cameras_id: list[int], tamanho_lote: int = 6):
    """
    Inicia os VisionWorkers agrupando as câmeras em lotes.
    """

    for idx in range(0, len(cameras_id), tamanho_lote):
        lote = cameras_id[idx:idx + tamanho_lote]

        # Filtra as câmeras que não possuem um worker ativo
        lote_novas: list[int] = []
        for camera in lote:
            if camera not in workers:
                lote_novas.append(camera)

        if not lote_novas:
            continue

        lote_novas.sort()  # Ordena para consistência na criação de workers

        worker = VisionWorker(cameras_lote=lote_novas)
        worker.start()

        for camera_id in lote_novas:
            workers[camera_id] = worker

        print(f"🎥 Worker de lote iniciado para as câmeras: {lote_novas}")

def parar_vision_workers():
    """Finaliza todos os workers de forma segura (sem duplicar chamadas)."""
    workers_unicos = set(workers.values())

    print(f"🛑 Parando {len(workers_unicos)} workers de visão...")

    for worker in workers_unicos:
        worker.stop()

    workers.clear()


def get_camera_status(camera_id: int) -> str:
    """Retorna o status da câmera especificada."""
    worker = workers.get(camera_id)

    if not worker:
        return 'Inativo'

    return 'Ativo' if worker.is_online(camera_id) else 'Desconectado'

def notificar_atualizacao_camera(camera_id: int):
    """
        Notifica o worker da atualização na câmera especificada.
    """
    worker = workers.get(camera_id)

    if worker:
        worker.update_camera(camera_id)

def notificar_atualizacao_zonas(camera_id: int):
    """
    Notifica o worker da câmera especificada para recarregar as zonas de monitoramento.
    """
    worker = workers.get(camera_id)

    if worker:
        worker.reload_zones(camera_id)

def notificar_desligamento_camera(camera_id: int):
    """
    Notifica o worker da câmera especificada para desligar.
    """
    worker = workers.get(camera_id)

    if worker:
        if len(worker.cameras) <= 1:
            worker.stop()

        del workers[camera_id]
        print(f"🛑 Worker para a câmera {camera_id} foi desligado.")