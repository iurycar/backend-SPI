from worker.vision_worker import VisionWorker

workers: dict[int, VisionWorker] = {}
MAX_CAMERAS_POR_WORKER = 6  # Limite de câmeras por worker para evitar sobrecarga

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
    Adiciona ou atualiza a câmera no worker correspondente.
    Se a câmera já estiver em um worker, apenas reinicia aquele worker.
    Se for nova, tenta encaixar em um worker com vaga (< MAX_CAMERAS_POR_WORKER).
    """
    worker = workers.get(camera_id)

    if worker:
        # Câmera já pertencia a um worker, apenas reinicia ele
        worker.update_camera(camera_id)
    else:
        # Câmera nova: procura um worker existente com espaço vago
        worker_com_vaga = None
        for w in set(workers.values()):
            if len(w.cameras) < MAX_CAMERAS_POR_WORKER:
                worker_com_vaga = w
                break

        if worker_com_vaga:
            print(f"🔄 Encaixando câmera {camera_id} no worker existente com câmeras {worker_com_vaga.cameras}...")
            workers[camera_id] = worker_com_vaga
            worker_com_vaga.update_camera(camera_id)
        else:
            print(f"🎥 Nenhum worker com vaga encontrado. Criando novo lote para câmera {camera_id}...")
            iniciar_vision_workers([camera_id], tamanho_lote=MAX_CAMERAS_POR_WORKER)

def notificar_desligamento_camera(camera_id: int):
    """
    Para a captura e libera os recursos físicos/RTSP da câmera deletada.
    """
    worker = workers.get(camera_id)

    if not worker:
        return

    # Remove a referência do dicionário global
    del workers[camera_id]

    # Remove da lista de câmeras do worker
    if camera_id in worker.cameras:
        worker.cameras.remove(camera_id)

    # Se não sobraram mais câmeras nesse worker, encerra o processo de vez
    if len(worker.cameras) == 0:
        worker.stop()
        print(f"🛑 Worker encerrado completamente pois não restam câmeras.")
    else:
        # Se ainda há outras câmeras no worker, reinicia o processo para liberar o descritor da excluída
        print(f"🔄 Reiniciando worker para as câmeras restantes: {worker.cameras}")
        worker.stop()
        worker.frame_queues.clear()
        worker.reload_zones_events.clear()
        worker.start()

    print(f"🛑 Câmera {camera_id} desligada e recursos liberados com sucesso.")

def notificar_atualizacao_zonas(camera_id: int):
    """
    Notifica o worker da câmera especificada para recarregar as zonas de monitoramento.
    """
    worker = workers.get(camera_id)

    if worker:
        worker.reload_zones(camera_id)