import multiprocessing as mp
import time

from services.visao_service import VisaoService
from connection.conn import Connection

class VisionWorker:
    def __init__(self, camera_id=1):
        self.camera_id = camera_id
        self.process = None
        self.stop_event = None
        self.frame_queue = None
        self.last_results = mp.Manager().dict()

    def start(self):
        if self.process is not None and self.process.is_alive():
            return

        self.stop_event = mp.Event()
        self.frame_queue = mp.Queue(maxsize=1)
        self.last_results = mp.Manager().dict()
        self.last_results['detections'] = []
        self.last_results['class_count'] = {}

        self.process = mp.Process(
            target=self._run,
            # REMOVA 'connection' DOS ARGUMENTOS:
            args=(self.camera_id, self.frame_queue, self.last_results, self.stop_event),
            daemon=True,
        )

        self.process.start()

    def stop(self):
        if self.stop_event is not None:
            self.stop_event.set()

        if self.process is not None and self.process.is_alive():
            self.process.join(timeout=3)

    def _run(self, camera_id, frame_queue, last_results, stop_event):
        try:
            from connection.conn import Connection
            connection = Connection().get_connection()

            visao_service = VisaoService(connection)

            visao_service.run_video_loop(
                camera_id=camera_id,
                frame_queue=frame_queue,
                last_results=last_results,
                stop_event=stop_event,
            )

        except Exception as exc:
            print(f"❌ Worker de visão falhou: {exc}")

    def next_frame(self):
        if self.frame_queue is None:
            return None

        try:
            return self.frame_queue.get_nowait()
        except Exception:
            return None

    def get_last_results(self):
        if self.last_results is None:
            return []
        return self.last_results.get('detections', [])
