"""
Pipeline desacoplado:

    [CameraReader]  --(LatestSlot)-->  [Inferência]  --(overlay)-->  [DisplayPublisher] --> fila MJPEG
         |                                                                  ^
         +------------------------(LatestSlot, frame cru)-------------------+

- O leitor SEMPRE sobrescreve o slot com o frame mais novo (nunca acumula fila => sem latência crescente).
- A inferência consome o frame mais novo no ritmo que consegue e descarta o resto.
- O publicador desenha o ÚLTIMO overlay conhecido sobre o frame cru mais novo, então o vídeo sai a
  ~30 FPS e com latência de ~1 frame, independente de quanto a inferência demora.
- Se ninguém está assistindo, o publicador não gasta CPU com resize/desenho/JPEG.
"""
import os
import threading
import time

import cv2

from core.stage_profiler import StageProfiler


# --------------------------------------------------------------------------- utilidades
class LatestSlot:
    """Guarda só o item mais recente; consumidores esperam por um item mais novo que o que já viram."""

    def __init__(self):
        self._cond = threading.Condition()
        self._item = None
        self._seq = 0

    def put(self, item) -> int:
        with self._cond:
            self._item = item
            self._seq += 1
            self._cond.notify_all()
            return self._seq

    def peek(self):
        with self._cond:
            return self._seq, self._item

    def wait_newer(self, last_seq: int, timeout: float = 0.2):
        """Retorna (seq, item) se houver item mais novo que last_seq; senão (last_seq, None)."""
        with self._cond:
            if self._seq <= last_seq:
                self._cond.wait(timeout)
            if self._seq > last_seq:
                return self._seq, self._item
            return last_seq, None


class TTLCache:
    """Cache com validade. O loader roda FORA do lock, então I/O lento não trava outras threads."""

    def __init__(self, ttl: float):
        self.ttl = ttl
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key, loader):
        now = time.monotonic()
        with self._lock:
            hit = self._data.get(key)
            if hit is not None and hit[0] > now:
                return hit[1]
        try:
            value = loader()
        except Exception:
            if hit is not None:        # falha no banco: usa o valor antigo em vez de derrubar o loop
                return hit[1]
            raise
        with self._lock:
            self._data[key] = (now + self.ttl, value)
        return value

    def invalidate(self, key=None) -> None:
        with self._lock:
            if key is None:
                self._data.clear()
            else:
                self._data.pop(key, None)


class TTLGate:
    """Deixa passar uma chave no máximo 1x a cada `ttl` segundos (cooldown local, sem rede)."""

    def __init__(self):
        self._exp: dict = {}
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    def allow(self, key, ttl: float) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last_prune > 60:
                self._exp = {k: v for k, v in self._exp.items() if v > now}
                self._last_prune = now
            if self._exp.get(key, 0.0) > now:
                return False
            self._exp[key] = now + ttl
            return True


def apply_transform(frame, rotacao, espelhar_h, espelhar_v):
    """Mesma lógica de VisaoService.aplicar_transformacoes_frame, sem consultar o banco."""
    if rotacao in (90, -270):
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif rotacao in (180, -180):
        frame = cv2.rotate(frame, cv2.ROTATE_180)
    elif rotacao in (270, -90):
        frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rotacao not in (0, None):
        h, w = frame.shape[:2]
        m = cv2.getRotationMatrix2D((w // 2, h // 2), -rotacao, 1.0)
        frame = cv2.warpAffine(frame, m, (w, h))

    if espelhar_h and espelhar_v:
        frame = cv2.flip(frame, -1)
    elif espelhar_h:
        frame = cv2.flip(frame, 1)
    elif espelhar_v:
        frame = cv2.flip(frame, 0)
    return frame


def tune_capture(cap) -> None:
    """
    Ajustes que mudam muito o FPS real da captura.
    - Webcam V4L2: o padrão costuma ser YUYV (cru), limitado pela banda USB (5-10 FPS em 720p/1080p).
      Pedir MJPG destrava 30 FPS.
    - Buffer de 1 frame para não acumular atraso.
    """
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        backend = (cap.getBackendName() or "").upper()
        if backend == "V4L2":
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(os.getenv("WEBCAM_WIDTH", "1280")))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(os.getenv("WEBCAM_HEIGHT", "720")))
            cap.set(cv2.CAP_PROP_FPS, int(os.getenv("WEBCAM_FPS", "30")))
    except Exception:
        pass


# --------------------------------------------------------------------------- leitor
class CameraReader(threading.Thread):
    """
    Lê a câmera o mais rápido que a fonte entrega e publica SEMPRE o frame mais novo.
    `cap.grab()` decodifica; `cap.retrieve()` (conversão para BGR + cópia) só roda quando o frame
    vai ser usado, o que permite limitar com `max_fps` sem perder a sincronia com o stream.
    """

    def __init__(self, cam_id: int, open_fn, transform_fn, slot: LatestSlot,
                 stop_event, profiler: StageProfiler, max_fps: float = 0.0):
        super().__init__(daemon=True, name=f"reader-{cam_id}")
        self.cam_id = cam_id
        self.open_fn = open_fn            # VisaoService.open_camera(cam_id) -> cv2.VideoCapture | None
        self.transform_fn = transform_fn  # (frame, cam_id) -> frame   (usar versão com cache!)
        self.slot = slot
        self.stop_event = stop_event
        self.prof = profiler
        self.min_interval = 1.0 / max_fps if max_fps > 0 else 0.0
        self.connected = False
        self.last_frame_wall = 0.0

    def run(self):
        cap = None
        retry_at = 0.0
        last_retrieve = 0.0
        label = f"cam{self.cam_id}.capture_fps"

        while not self.stop_event.is_set():
            if cap is None or not cap.isOpened():
                self.connected = False
                now = time.monotonic()
                if now < retry_at:
                    time.sleep(0.05)
                    continue
                retry_at = now + 1.0
                cap = self.open_fn(self.cam_id)
                if cap is None or not cap.isOpened():
                    if cap is not None:
                        cap.release()
                    cap = None
                    time.sleep(0.1)
                    continue
                tune_capture(cap)

            t0 = time.perf_counter()
            if not cap.grab():
                self.connected = False
                cap.release()
                cap = None
                retry_at = time.monotonic() + 1.0
                continue
            t_cap = time.monotonic()          # instante real da captura (base da latência ponta a ponta)

            if self.min_interval and (t_cap - last_retrieve) < self.min_interval:
                continue
            ok, frame = cap.retrieve()
            self.prof.add("reader.grab+retrieve", (time.perf_counter() - t0) * 1000.0)
            if not ok or frame is None or frame.size == 0:
                continue
            last_retrieve = t_cap

            with self.prof.stage("reader.transform"):
                frame = self.transform_fn(frame, self.cam_id)

            self.slot.put((frame, t_cap))
            self.connected = True
            self.last_frame_wall = time.time()
            self.prof.tick(label)

        if cap is not None:
            cap.release()
            print(f"🛑 Leitor da câmera {self.cam_id} finalizado e liberado.")


# --------------------------------------------------------------------------- publicador
class DisplayPublisher(threading.Thread):
    """Gera o MJPEG: frame cru mais novo + último overlay, em ritmo próprio (não espera a inferência)."""

    VIEWER_GRACE_S = 3.0

    def __init__(self, cam_id: int, raw_slot: LatestSlot, overlay_store: dict, frame_queue,
                 viewer_ts, stop_event, draw_fn, profiler: StageProfiler,
                 target_fps: float = 30.0, stream_width: int = 960, jpeg_quality: int = 75):
        super().__init__(daemon=True, name=f"display-{cam_id}")
        self.cam_id = cam_id
        self.raw_slot = raw_slot
        self.overlay_store = overlay_store   # {cam_id: overlay dict}; troca de referência é atômica
        self.queue = frame_queue
        self.viewer_ts = viewer_ts           # mp.Value('d') com o último "alguém pediu frame"; None = sempre ativo
        self.stop_event = stop_event
        self.draw_fn = draw_fn               # (img, overlay, scale) -> None
        self.prof = profiler
        self.period = 1.0 / target_fps if target_fps > 0 else 0.0
        self.stream_width = stream_width
        self.jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]

    def _has_viewer(self) -> bool:
        if self.viewer_ts is None:
            return True
        return (time.time() - self.viewer_ts.value) < self.VIEWER_GRACE_S

    def _publish(self, data: bytes) -> None:
        if self.queue is None:
            return
        try:
            if self.queue.full():
                self.queue.get_nowait()      # descarta o antigo: o espectador sempre vê o mais novo
        except Exception:
            pass
        try:
            self.queue.put(data, block=False)
        except Exception:
            pass

    def run(self):
        last_seq = 0
        last_pub = 0.0
        fps_label = f"cam{self.cam_id}.display_fps"

        while not self.stop_event.is_set():
            seq, item = self.raw_slot.wait_newer(last_seq, timeout=0.2)
            if item is None:
                continue
            last_seq = seq

            now = time.monotonic()
            if self.period and (now - last_pub) < self.period * 0.9:
                continue
            if not self._has_viewer():
                continue
            last_pub = now

            frame, t_cap = item
            overlay = self.overlay_store.get(self.cam_id)
            h, w = frame.shape[:2]

            with self.prof.stage("display.resize"):
                if self.stream_width and w > self.stream_width:
                    scale = self.stream_width / w
                    img = cv2.resize(frame, (self.stream_width, int(h * scale)),
                                     interpolation=cv2.INTER_LINEAR)
                else:
                    scale = 1.0
                    img = frame.copy() if overlay else frame   # só copia se for desenhar

            if overlay:
                with self.prof.stage("display.draw"):
                    self.draw_fn(img, overlay, scale)

            with self.prof.stage("display.jpeg"):
                ok, buf = cv2.imencode(".jpg", img, self.jpeg_params)
            if not ok:
                continue

            self._publish(buf.tobytes())
            self.prof.add("e2e.capture_to_display", (time.monotonic() - t_cap) * 1000.0)
            self.prof.tick(fps_label)