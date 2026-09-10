import multiprocessing as mp
import time

from services.visao_service import VisaoService
from connection.conn import Connection

class VisionWorker:
    def __init__(self, cameras_lote: list[int] = None, camera_id: int = None):

        if cameras_lote is not None:
            self.cameras = list(cameras_lote)
        elif camera_id is not None:
            self.cameras = [camera_id]
        else:
            raise ValueError("É necessário fornecer 'cameras_lote' ou 'camera_id'.")

        self.process = None
        self.stop_event = None
        self.reload_zones_events = {}
        self.frame_queues = {}
        self.manager = mp.Manager()
        self.last_results = self.manager.dict()

    def start(self) -> None:
        if self.process is not None and self.process.is_alive():
            return

        self.stop_event = mp.Event()

        for camera_id in self.cameras:
            self.reload_zones_events[camera_id] = mp.Event() # Evento para sinalizar recarregamento de zonas
            self.frame_queues[camera_id] = mp.Queue(maxsize=1) # Fila de tamanho 1 para armazenar apenas o último frame

            # Inicializa o dicionário de resultados para cada câmera
            camera_data = self.manager.dict()
            camera_data['detections'] = []
            camera_data['class_count'] = {}
            camera_data['connected'] = False
            camera_data['last_frame_time'] = 0
            self.last_results[camera_id] = camera_data


        self.process = mp.Process(
            target=self._run_batch,
            args=(self.cameras, 
                self.frame_queues, 
                self.last_results, 
                self.stop_event, 
                self.reload_zones_events
            ),
            daemon=True,
        )

        self.process.start()
    
        
    def reload_zones(self, camera_id: int = None) -> None:
        if camera_id:
            event = self.reload_zones_events.get(camera_id)
            if event:
                event.set()
                print(f"🔄 Worker de visão para a câmera {camera_id} recebeu sinal para recarregar zonas.")
        else:
            for cam_id, event in self.reload_zones_events.items():
                if event:
                    event.set()
                    print(f"🔄 Worker de visão para a câmera {cam_id} recebeu sinal para recarregar zonas.")


    def stop(self) -> None:
        
        if self.stop_event is not None:
            self.stop_event.set()

        if self.process is not None and self.process.is_alive():
            self.process.join(timeout=3)


    def _run_batch(self, cameras, frame_queues, last_results, stop_event, reload_zones_events) -> None:
        try:
            from connection.conn import Connection
            connection = Connection().get_connection()

            visao_service = VisaoService(connection)

            visao_service.run_batch_video_loop(
                cameras=cameras,
                frame_queues=frame_queues,
                last_results=last_results,
                stop_event=stop_event,
                reload_zones_events=reload_zones_events,
            )

        except Exception as exc:
            print(f"❌ Worker de lote falhou: {exc}")

    def next_frame(self, camera_id: int = None) -> bytes | None:
        if camera_id is None:
            return None

        queue = self.frame_queues.get(camera_id)

        if not queue:
            return None
        
        try:
            return queue.get_nowait()
        except Exception:
            return None

    def get_last_results(self, camera_id: int = None) -> list:
        target_id = camera_id or self.cameras[0]
        response = self.last_results.get(target_id)

        if response is None:
            return []

        return response.get('detections', [])

    def is_online(self, camera_id: int = None) -> bool:
        """
            Retorna True se o processo estiver vivo e se recebeu um frame nos últimos 5 segundos.
        """

        if not self.process or not self.process.is_alive():
            return False

        target_id = camera_id or self.cameras[0]
        cam_info = self.last_results.get(target_id)

        if not cam_info:
            return False
        
        connected = cam_info.get('connected', False)
        last_frame_time = cam_info.get('last_frame_time', 0)

        return connected and (time.time() - last_frame_time) < 5
