import logging
import os
import threading
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import psycopg2

from core.stage_profiler import StageProfiler
from core.tipo_deteccao import TIPOS_POSTURA
from core.vision_metrics import FrameMetrics
from services.visao_service import MODEL_PATH, MODEL_PATH_POSE, VisaoService
from worker.vision_pipeline import (
    CacheComTTL,
    CameraReader,
    UltimoFrameContainer,
    DisplayPublisher,
    LimitadorTempoChave,
    aplicar_transformacoes,
)
logger = logging.getLogger(__name__)

"""
VisaoServiceOptimized — substitui o loop de execução contínua com foco em alto desempenho.

Principais otimizações em relação ao serviço básico:
  1. Pipeline desacoplado: Captura, inferência e publicação rodam em threads separadas.
  2. Rastreamento isolado: Cria uma instância independente de ByteTrack para cada câmera.
  3. Estimativa de postura em cadência adaptativa: Evita executar o modelo pesado de pose em todos os frames.
  4. Processamento de efeitos colaterais em segundo plano (alertas no banco, ESP32 e estatísticas).
  5. Camada de cache para setores e zonas em memória RAM.
"""

def _imgsz_env(name: str, default: str):
    parts = [int(p) for p in os.getenv(name, default).replace("x", ",").split(",") if p.strip()]
    return parts[0] if len(parts) == 1 else parts      # int ou [alto, largura]


class VisaoServiceOptimized(VisaoService):
    # ------------------------------------------------------------------ configuração
    BACKEND = os.getenv("VISION_BACKEND", "openvino").lower()
    DET_IMGSZ = _imgsz_env("DET_IMGSZ", "640")
    POSE_IMGSZ = _imgsz_env("POSE_IMGSZ", "480")

    DET_CONF, DET_IOU, DET_MIN_CONF = 0.3, 0.4, 0.5      # idênticos ao código original
    POSE_CONF = 0.5

    STREAM_FPS = float(os.getenv("STREAM_FPS", "30"))
    STREAM_WIDTH = int(os.getenv("STREAM_WIDTH", "960"))
    JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "75"))
    CAPTURE_MAX_FPS = float(os.getenv("CAPTURE_MAX_FPS", "0"))

    POSE_ACTIVE_INTERVAL = float(os.getenv("POSE_ACTIVE_INTERVAL", "0.2"))
    POSE_IDLE_INTERVAL = float(os.getenv("POSE_IDLE_INTERVAL", "1.0"))
    POSE_IDLE_AFTER = float(os.getenv("POSE_IDLE_AFTER", "3.0"))
    POSE_MAX_DUTY = float(os.getenv("POSE_MAX_DUTY", "0.35"))

    TRACK_FPS = {"det": int(os.getenv("TRACK_FPS", "15")),
                 "pose": max(1, int(round(1.0 / float(os.getenv("POSE_ACTIVE_INTERVAL", "0.2")))))}
    OVERLAY_MAX_AGE = 1.5     # não desenha resultado mais velho que isso (inferência travada)

    ESQUELETO_CONEXOES = [
        (0, 1), (0, 2), (1, 3), (2, 4),
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12),
        (11, 13), (13, 15), (12, 14), (14, 16),
    ]

    def __init__(self, connection):
        super().__init__(connection)
        self.profiler = StageProfiler("vision")
        self._alert_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alerts")
        self._gate = LimitadorTempoChave()
        self._setor_cache = CacheComTTL(ttl=60.0)
        self._trackers: dict = {}
        self._zone_geo: dict = {}
        self._pose_state: dict = {}
        self._postura_inicio: dict = {}      # (cam, track, tipo) -> [inicio, ultimo_visto]
        self._postura_emitido: dict = {}     # (cam, track, tipo) -> instante até o qual está em cooldown
        self._al_on = False
        self._al_check_at = 0.0
        self._last_err_log = 0.0
        self._n_cams = 1

    # ------------------------------------------------------------------ modelos
    def _resolve_model(self, pt_path: str) -> str:
        if self.BACKEND != "pt":
            base = os.path.splitext(pt_path)[0]
            cand = {"openvino": base + "_openvino_model",
                    "ncnn": base + "_ncnn_model",
                    "onnx": base + ".onnx"}.get(self.BACKEND)
            if cand and os.path.exists(cand):
                return cand
            print(f"⚠️ VISION_BACKEND={self.BACKEND}, mas '{cand}' não existe "
                  f"(rode scripts/export_models.py). Usando PyTorch (.pt).")
        return pt_path

    def _ensure_models_loaded(self):
        if self.modelo is not None and self.modelo_pose is not None:
            return
        from ultralytics import YOLO

        det_path = self._resolve_model(MODEL_PATH)
        pose_path = self._resolve_model(MODEL_PATH_POSE)
        self.modelo = YOLO(det_path, task="detect")
        self.modelo_pose = YOLO(pose_path, task="pose")
        print(f"🧠 Modelos carregados: det={os.path.basename(det_path)} pose={os.path.basename(pose_path)}")

        # Warm-up: a 1ª inferência é bem mais lenta (alocação, oneDNN/OpenVINO compilando kernels)
        dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
        for _ in range(2):
            self.modelo.predict(dummy, imgsz=self.DET_IMGSZ, verbose=False)
            self.modelo_pose.predict(dummy, imgsz=self.POSE_IMGSZ, verbose=False)

    def _configure_threads(self):
        cv2.setNumThreads(int(os.getenv("VISION_CV_THREADS", "2")))
        # Zen 3 = SMT: usar núcleos físicos. Com N workers, divida: cores_físicos // N.
        n = int(os.getenv("VISION_TORCH_THREADS", "0")) or max(1, (os.cpu_count() or 2) // 2)
        try:
            import torch
            torch.set_num_threads(n)
        except Exception:
            pass

    def _tracker(self, kind: str, cam_id: int):
        key = (kind, cam_id)
        tracker = self._trackers.get(key)
        if tracker is None:
            import yaml
            from ultralytics.trackers.byte_tracker import BYTETracker
            from ultralytics.utils import IterableSimpleNamespace
            from ultralytics.utils.checks import check_yaml

            yaml_path = check_yaml("bytetrack.yaml")
            with open(yaml_path, "r", encoding="utf-8") as f:
                cfg_dict = yaml.safe_load(f)

            # Define o FPS diretamente na configuração do tracker
            fps = self.TRACK_FPS[kind]
            cfg_dict["fps"] = fps
            cfg_dict["frame_rate"] = fps

            cfg = IterableSimpleNamespace(**cfg_dict)
            tracker = BYTETracker(args=cfg)
            self._trackers[key] = tracker
        return tracker

    def _predict_tracked(self, model, kind: str, cam_id: int, frame, imgsz, conf, iou=None):
        """predict() + ByteTrack por câmera. Registra pré/inferência/pós-processamento do YOLO."""
        prof = self.profiler
        kw = dict(imgsz=imgsz, conf=conf, verbose=False)
        if iou is not None:
            kw["iou"] = iou

        with prof.etapa(f"{kind}.predict(total)"):
            r = model.predict(frame, **kw)[0]

        speed = getattr(r, "speed", None) or {}
        for k in ("preprocess", "inference", "postprocess"):    # tempos internos do ultralytics (ms)
            if k in speed:
                prof.adicionar_tempo(f"{kind}.{k}", speed[k])

        with prof.etapa(f"{kind}.track"):
            if r.boxes is None:
                tracks = np.empty((0, 8), dtype=np.float32)
            else:
                tracks = np.asarray(self._tracker(kind, cam_id).update(r.boxes.cpu().numpy(), frame),
                                    dtype=np.float32)
                if tracks.size == 0:
                    tracks = np.empty((0, 8), dtype=np.float32)
                elif tracks.ndim != 2 or tracks.shape[1] < 8:
                    raise RuntimeError("ultralytics >= 8.1 é necessário (BYTETracker deve retornar a coluna idx).")
        return r, tracks

    # ------------------------------------------------------------------ caches / efeitos colaterais
    def _carregar_zonas(self, cam_id: int):
        zonas = self._zonas_de_monitoramento(cam_id)
        self._zone_geo.pop(cam_id, None)
        self._setor_cache.invalidar()
        for z in zonas:                       # pré-carrega: o 1º frame com detecção não paga consulta
            try:
                self._id_setor_da_zona(z.id)
            except Exception:
                pass
        return zonas

    def _zone_geometry(self, cam_id: int, w: int, h: int, zonas):
        cached = self._zone_geo.get(cam_id)
        if cached is not None and cached[0] == (w, h) and cached[1] is zonas:
            return cached[2]
        geo = [(z, self.regiao_para_caixa(self.regiao_para_pixels(z.regiao, w, h))) for z in zonas]
        self._zone_geo[cam_id] = ((w, h), zonas, geo)
        return geo

    def _id_setor_da_zona(self, zona_id):
        def load():
            setor = self.setores_repository.get_setor_por_id_zona(zona_id)
            return setor.id if setor else None
        return self._setor_cache.obter(zona_id, load)

    def _active_learning_on(self) -> bool:
        now = time.monotonic()
        if now >= self._al_check_at:                  # 1 leitura de disco a cada 2 s (antes: a cada frame)
            self._al_check_at = now + 2.0
            try:
                with open(self.flag_path, "r") as f:
                    self._al_on = f.read().strip() == "1"
            except OSError:
                self._al_on = False
        return self._al_on

    def _submit(self, fn, *args, **kwargs):
        """Executa efeito colateral (banco, Redis, ESP32) fora do loop de inferência, serializado."""
        def run():
            try:
                fn(*args, **kwargs)
            except psycopg2.Error as exc:
                try:
                    self.connection.rollback()
                except Exception:
                    pass
                logger.warning("Efeito colateral falhou (SQLSTATE %s).", getattr(exc, "pgcode", None))
            except Exception as exc:
                logger.warning("Efeito colateral falhou: %s", exc)
        self._alert_pool.submit(run)

    def _alerta_epi(self, zona, evento: str, track_id: int, severidade: int):
        if zona.id_monitorar is None:
            return
        if not self._gate.permitir(("epi", zona.id_monitorar, evento, track_id), 30):    # mesmo cooldown de 30 s
            return
        self._submit(VisaoService._registrar_alerta_epi_incorreto, self, zona, evento, track_id,
                     severidade=severidade)

    def _amostra(self, id_setor, track_id: int, conforme: bool):
        if not id_setor or track_id == -1:
            return
        if not self._gate.permitir(("stats", id_setor, track_id), 10):                   # mesmo cooldown de 10 s
            return
        self._submit(VisaoService._registrar_amostra_estatistica, self, id_setor, track_id, conforme)

    def _monitorar_tempo_postura(self, camera_id: int, track_id: int, tipo_deteccao: str, motivo: str,
                                 ativo: bool, tempo_limite_segundos: int = 10, severidade: int = 1) -> None:
        """Mesma regra do original (persistência mínima + cooldown de 45 s), mas em memória:
        antes eram ~6 round-trips ao Redis por pessoa, por tipo, por frame (+ um print por frame)."""
        if tipo_deteccao not in TIPOS_POSTURA:
            raise ValueError(f"tipo_deteccao '{tipo_deteccao}' inválido para postura.")

        key = (camera_id, track_id, tipo_deteccao)
        now = time.monotonic()

        if not ativo:
            self._postura_inicio.pop(key, None)
            self._postura_emitido.pop(key, None)
            return

        reg = self._postura_inicio.get(key)
        if reg is None or now - reg[1] > 60:          # equivalente ao TTL de 60 s da chave no Redis
            reg = [now, now]
            self._postura_inicio[key] = reg
        reg[1] = now

        if self._postura_emitido.get(key, 0.0) > now:
            return
        decorrido = now - reg[0]
        if decorrido >= tempo_limite_segundos:
            self._postura_emitido[key] = now + 45
            self._submit(self._emitir_alerta_postura, camera_id, track_id, tipo_deteccao, motivo,
                         severidade, decorrido)

        if len(self._postura_inicio) > 2000:          # limpeza de tracks que sumiram
            self._postura_inicio = {k: v for k, v in self._postura_inicio.items() if now - v[1] < 60}

    def _emitir_alerta_postura(self, camera_id, track_id, tipo_deteccao, motivo, severidade, decorrido):
        setor = self.setores_repository.get_setor_por_id_camera(camera_id)
        if not setor:
            logger.warning("Setor não encontrado para a câmera %s. Não é possível registrar alerta de postura.",
                           camera_id)
            return
        responsaveis = self.setores_repository.get_responsaveis_por_setor(setor.id)
        sucesso = self.alertas_service.criar_alerta(
            monitoramento=None,
            id_usuario=responsaveis[0] if responsaveis else None,
            evento=f"Má postura detectada: {motivo}",
            severidade=severidade,
            destinatarios=responsaveis,
            tipo_deteccao=tipo_deteccao,
            id_camera=camera_id,
        )
        if sucesso:
            print(f"⚠️ Alerta emitido: {tipo_deteccao} contínua ({int(decorrido)}s) - Track ID: {track_id}")

    # ------------------------------------------------------------------ detecção (sem desenhar)
    def _detect_frame(self, cam_id: int, frame, zonas):
        prof = self.profiler
        h, w = frame.shape[:2]
        detections: list[dict] = []
        class_count: dict = defaultdict(int)
        overlay: list = []

        r, tracks = self._predict_tracked(self.modelo, "det", cam_id, frame,
                                          self.DET_IMGSZ, self.DET_CONF, self.DET_IOU)

        with prof.etapa("det.rules"):
            if r.boxes is not None and len(r.boxes) and self._active_learning_on():
                self._processar_active_learning(frame, r.boxes, (h, w))   # frame cru: ninguém o altera mais

            geo = self._zone_geometry(cam_id, w, h, zonas)
            names = self.modelo.names

            for x1, y1, x2, y2, tid, conf, cls, _ in tracks.tolist():
                if conf < self.DET_MIN_CONF:
                    continue

                track_id = int(tid)
                xyxy = (int(x1), int(y1), int(x2), int(y2))
                label_name = names[int(cls)].lower()
                classe_epi = self._classe_epi_por_label(label_name)
                nome = label_name.capitalize().replace("_", " ")
                zonas_do_objeto = []

                for zona, caixa in geo:
                    if not self._caixas_intersectam(xyxy, caixa):
                        continue

                    if self._zona_requer_classe(zona.epis_categoria, classe_epi, zona.permitido):
                        zonas_do_objeto.append(zona.id)
                        id_setor = self._id_setor_da_zona(zona.id)

                        if label_name.startswith("sem_"):
                            overlay.append(("box", xyxy, nome, "vermelho"))
                            self._alerta_epi(zona, f"Sem EPI necessário: {classe_epi}", track_id, 2)
                            self._amostra(id_setor, track_id, False)
                        elif label_name.endswith("_chapeu"):
                            overlay.append(("box", xyxy, nome, "amarelo"))
                            self._alerta_epi(zona, f"Equipamento inadequado: {classe_epi}", track_id, 1)
                            self._amostra(id_setor, track_id, False)
                        elif label_name.endswith("_normal"):
                            overlay.append(("box", xyxy, nome.replace("normal", ""), "verde"))
                            self._amostra(id_setor, track_id, True)
                        else:
                            overlay.append(("box", xyxy, nome, "verde"))
                            self._amostra(id_setor, track_id, True)

                    if label_name == "pessoa":
                        if not self._zona_requer_classe(zona.epis_categoria, "pessoa", zona.permitido):
                            overlay.append(("box", xyxy, f"Pessoa ID:{track_id} (Zona Restrita)", "vermelho"))
                            self._alerta_epi(zona, "Pessoa em zona restrita", track_id, 3)
                        else:
                            overlay.append(("box", xyxy, f"Pessoa ID:{track_id}", "branco"))

                class_count[label_name] += 1
                for z_id in zonas_do_objeto:
                    detections.append({"id": track_id, "label": label_name, "confidence": conf, "zona": z_id})

        return detections, class_count, overlay

    # ------------------------------------------------------------------ pose (sem desenhar)
    def _pose_frame(self, cam_id: int, frame) -> list[dict]:
        prof = self.profiler
        pessoas: list[dict] = []

        r, tracks = self._predict_tracked(self.modelo_pose, "pose", cam_id, frame,
                                          self.POSE_IMGSZ, self.POSE_CONF)

        with prof.etapa("pose.rules"):
            if r.keypoints is None or len(tracks) == 0:
                return pessoas

            kps_all = r.keypoints.xy.cpu().numpy()
            for row in tracks:
                idx = int(row[7])
                track_id = int(row[4])
                if idx >= len(kps_all):
                    continue
                individual = kps_all[idx]
                if len(individual) < 17:
                    continue

                ombro_esq, ombro_dir = individual[5], individual[6]
                quadril_esq, quadril_dir = individual[11], individual[12]
                joelho_esq, joelho_dir = individual[13], individual[14]
                tornozelo_esq, tornozelo_dir = individual[15], individual[16]

                cor_coluna = "ciano"
                coluna = None
                pontos_validos = all(p[0] > 0 and p[1] > 0
                                     for p in (ombro_esq, ombro_dir, quadril_esq, quadril_dir))

                if not pontos_validos:
                    cor_coluna = "cinza"
                else:
                    is_ma, motivo, pt_ombro, pt_quadril = self._avaliar_postura(
                        "tronco", ombro_esq=ombro_esq, ombro_dir=ombro_dir,
                        quadril_esq=quadril_esq, quadril_dir=quadril_dir)
                    if is_ma:
                        cor_coluna = "vermelho"
                    coluna = (pt_ombro, pt_quadril)

                    self._monitorar_tempo_postura(camera_id=cam_id, track_id=track_id,
                                                  tipo_deteccao="postura_tronco",
                                                  motivo=motivo if is_ma else "Postura normal",
                                                  ativo=is_ma, tempo_limite_segundos=10, severidade=1)

                    is_rot, motivo_rot, _, _ = self._avaliar_postura(
                        "rotacao", ombro_esq=ombro_esq, ombro_dir=ombro_dir,
                        quadril_esq=quadril_esq, quadril_dir=quadril_dir)
                    self._monitorar_tempo_postura(camera_id=cam_id, track_id=track_id,
                                                  tipo_deteccao="postura_rotacao",
                                                  motivo=motivo_rot if is_rot else "Sem rotacao excessiva",
                                                  ativo=is_rot, tempo_limite_segundos=10, severidade=1)

                    is_caido, motivo_queda, _, _ = self._avaliar_postura(
                        "queda", ombro_esq=ombro_esq, ombro_dir=ombro_dir,
                        quadril_esq=quadril_esq, quadril_dir=quadril_dir,
                        joelho_esq=joelho_esq, joelho_dir=joelho_dir,
                        tornozelo_esq=tornozelo_esq, tornozelo_dir=tornozelo_dir)
                    self._monitorar_tempo_postura(camera_id=cam_id, track_id=track_id,
                                                  tipo_deteccao="queda",
                                                  motivo=motivo_queda if is_caido else "Em pé",
                                                  ativo=is_caido, tempo_limite_segundos=3, severidade=3)

                pessoas.append({"kp": individual, "coluna": coluna, "cor": cor_coluna})
        return pessoas

    # ------------------------------------------------------------------ desenho (roda no publicador)
    def draw_overlay(self, img, overlay: dict, scale: float) -> None:
        now = time.monotonic()

        if now - overlay.get("det_t", 0.0) < self.OVERLAY_MAX_AGE:
            for _, xyxy, label, cor in overlay.get("det", ()):
                box = [int(v * scale) for v in xyxy]
                self._desenhar_caixa_delimitadora(img, box, label, self.CORES.get(cor, (0, 255, 0)))

        if now - overlay.get("pose_t", 0.0) < self.OVERLAY_MAX_AGE:
            for p in overlay.get("pose", ()):
                pts = [(int(x * scale), int(y * scale)) for x, y in p["kp"]]
                for (x, y) in pts:
                    if x > 0 and y > 0:
                        cv2.circle(img, (x, y), 4, (0, 255, 180), -1, cv2.LINE_AA)
                        cv2.circle(img, (x, y), 5, (20, 20, 20), 1, cv2.LINE_AA)
                for a, b in self.ESQUELETO_CONEXOES:
                    (x1, y1), (x2, y2) = pts[a], pts[b]
                    if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:
                        cv2.line(img, (x1, y1), (x2, y2), (255, 180, 0), 2, cv2.LINE_AA)
                if p["coluna"] is not None:
                    o, q = p["coluna"]
                    cv2.line(img, (int(o[0] * scale), int(o[1] * scale)),
                             (int(q[0] * scale), int(q[1] * scale)),
                             self.CORES.get(p["cor"], (255, 255, 0)), 4, cv2.LINE_AA)

    # ------------------------------------------------------------------ processamento de 1 câmera
    def _process_camera(self, cam_id: int, frame, zonas, prev_overlay: dict | None):
        prof = self.profiler
        now = time.monotonic()

        with prof.etapa("total.det"):
            detections, class_count, det_overlay = self._detect_frame(cam_id, frame, zonas)

        st = self._pose_state.setdefault(cam_id, {"last_run": 0.0, "last_people": now, "ema": 0.0})
        if "pessoa" in class_count:
            st["last_people"] = now
        ocioso = (now - st["last_people"]) > self.POSE_IDLE_AFTER
        base = self.POSE_IDLE_INTERVAL if ocioso else self.POSE_ACTIVE_INTERVAL
        # Orçamento: com a CPU saturada o intervalo fixo não segura nada (a pose rodaria em todo ciclo).
        # Então o intervalo cresce até a pose ocupar no máx. POSE_MAX_DUTY do tempo do worker.
        duty = max(0.05, self.POSE_MAX_DUTY / max(1, self._n_cams))
        intervalo = max(base, st["ema"] / duty)

        pose = prev_overlay.get("pose", []) if prev_overlay else []
        pose_t = prev_overlay.get("pose_t", 0.0) if prev_overlay else 0.0
        if now - st["last_run"] >= intervalo:
            st["last_run"] = now
            t0 = time.perf_counter()
            with prof.etapa("total.pose"):
                pose = self._pose_frame(cam_id, frame)
            dur = time.perf_counter() - t0
            st["ema"] = dur if st["ema"] == 0.0 else 0.7 * st["ema"] + 0.3 * dur
            pose_t = time.monotonic()
            if pose:
                st["last_people"] = pose_t
            prof.marcar_evento(f"cam{cam_id}.pose_fps")

        overlay = {"det": det_overlay, "det_t": time.monotonic(), "pose": pose, "pose_t": pose_t}
        return detections, class_count, overlay

    # ------------------------------------------------------------------ loop principal
    def run_batch_video_loop(self, cameras, frame_queues, last_results, stop_event=None,
                             reload_zones_events=None, viewer_stamps=None):
        """
        Mantém a assinatura original (+ viewer_stamps opcional).
        Threads por câmera: leitor e publicador. Esta thread: só inferência + regras.
        """
        self._configure_threads()
        self._ensure_models_loaded()
        self._n_cams = len(cameras)
        prof = self.profiler
        stop = stop_event if stop_event is not None else threading.Event()

        transform_cache = CacheComTTL(ttl=5.0)

        def transform(frame, cam_id):
            t = transform_cache.obter(cam_id, lambda: self.cameras_service.obter_transformacoes_camera(cam_id))
            return frame if not t else aplicar_transformacoes(frame, *t)

        zonas_por_camera = {c: self._carregar_zonas(c) for c in cameras}
        metricas = {c: FrameMetrics() for c in cameras}
        overlay_store: dict = {}
        slots = {c: UltimoFrameContainer() for c in cameras}
        last_seq = defaultdict(int)
        last_hb = defaultdict(float)

        readers, publishers = {}, []
        for c in cameras:
            readers[c] = CameraReader(c, self.open_camera, transform, slots[c], stop, prof,
                                      fps_maximo=self.CAPTURE_MAX_FPS)
            readers[c].start()
            publishers.append(DisplayPublisher(
                c, slots[c], overlay_store,
                frame_queues.get(c) if frame_queues else None,
                viewer_stamps.get(c) if viewer_stamps else None,
                stop, self.draw_overlay, prof,
                fps_alvo=self.STREAM_FPS, largura_stream=self.STREAM_WIDTH, qualidade_jpeg=self.JPEG_QUALITY))
            publishers[-1].start()

        try:
            while not stop.is_set():
                if reload_zones_events:
                    for c in cameras:
                        ev = reload_zones_events.get(c)
                        if ev is not None and ev.is_set():
                            print(f"🔄 Recarregando zonas da câmera {c} no processo de visão...")
                            zonas_por_camera[c] = self._carregar_zonas(c)
                            ev.clear()

                trabalhou = False
                for c in cameras:
                    seq, item = slots[c].obter_atual()
                    if item is None or seq <= last_seq[c]:
                        continue
                    last_seq[c] = seq            # frames intermediários são descartados de propósito
                    frame, t_cap = item
                    trabalhou = True

                    t0 = time.perf_counter()
                    try:
                        detections, class_count, overlay = self._process_camera(
                            c, frame, zonas_por_camera[c], overlay_store.get(c))
                    except Exception as exc:     # uma câmera com problema não derruba as outras
                        if time.monotonic() - self._last_err_log > 5:
                            self._last_err_log = time.monotonic()
                            print(f"❌ Erro ao processar câmera {c}: {exc}")
                            traceback.print_exc()
                        continue

                    overlay_store[c] = overlay    # troca atômica de referência
                    prof.adicionar_tempo("total.frame", (time.perf_counter() - t0) * 1000.0)
                    prof.adicionar_tempo("e2e.capture_to_result", (time.monotonic() - t_cap) * 1000.0)
                    prof.marcar_evento(f"cam{c}.infer_fps")

                    # 1 única ida ao Manager por resultado (antes eram ~4 por frame de captura + 4 por resultado)
                    if last_results is not None and c in last_results:
                        try:
                            measurement = metricas[c].complete(t_cap, time.monotonic())
                            last_results[c].update({
                                "detections": detections,
                                "class_count": dict(class_count),
                                "result": dict(measurement, detections=detections, class_count=dict(class_count)),
                            })
                        except Exception:
                            pass

                now = time.monotonic()
                for c in cameras:                 # heartbeat de conexão a 1 Hz (antes: a cada frame)
                    if now - last_hb[c] >= 1.0 and last_results is not None and c in last_results:
                        last_hb[c] = now
                        try:
                            last_results[c].update({"connected": readers[c].connected,
                                                    "last_frame_time": readers[c].last_frame_wall})
                        except Exception:
                            pass

                if not trabalhou:
                    time.sleep(0.002)
                prof.emitir_relatorio()
                self._flush_estatisticas_para_banco()
        finally:
            print("🛑 Encerrando loop de visão em lote...")
            stop.set()
            for t in list(readers.values()) + publishers:
                t.join(timeout=2)
            self._alert_pool.shutdown(wait=False)
            prof.emitir_relatorio(forcar=True)
            self._flush_estatisticas_para_banco(forcar=True)