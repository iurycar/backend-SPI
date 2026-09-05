import multiprocessing as mp
import time

from services.visao_service import VisaoService
from connection.conn import Connection

class VisionWorker:
    def __init__(self, camera_id=1, alertas_queue=None):
        self.camera_id = camera_id
        self.alertas_queue = alertas_queue
        self.process = None
        self.stop_event = None
        self.last_results = mp.Manager().dict()

    def start(self):
        if self.process is not None and self.process.is_alive():
            return

        self.stop_event = mp.Event()
        self.last_results = mp.Manager().dict()
        self.last_results['detections'] = []
        self.last_results['class_count'] = {}
        self.last_results['last_frame'] = None

        self.process = mp.Process(
            target=self._run,
            # REMOVA 'connection' DOS ARGUMENTOS:
            args=(self.camera_id, self.last_results, self.stop_event, self.alertas_queue),
            daemon=True,
        )

        self.process.start()

    def stop(self):
        if self.stop_event is not None:
            self.stop_event.set()

        if self.process is not None and self.process.is_alive():
            self.process.join(timeout=3)

    def _run(self, camera_id, last_results, stop_event, alertas_queue):
        try:
            from connection.conn import Connection
            connection = Connection()

            visao_service = VisaoService(connection, alertas_queue=alertas_queue)

            visao_service.run_video_loop(
                camera_id=camera_id,
                last_results=last_results,
                stop_event=stop_event,
            )

        except Exception as exc:
            print(f"❌ Worker de visão falhou: {exc}")

    def next_frame(self):
        if self.last_results is None:
            return None

        return self.last_results.get('last_frame')

    def get_last_results(self):
        if self.last_results is None:
            return []
        return self.last_results.get('detections', [])
