
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from ultralytics import YOLO
import numpy as np
import threading
import traceback
import platform
import psycopg2
import logging
import redis
import math
import time
import cv2
import os

from core.alerta_diagnostics import trace_alert_candidate
from core.stage_profiler import StageProfiler
from tasks.alarme_task import enviar_comando
from core.tipo_deteccao import TIPOS_POSTURA
from core.vision_metrics import FrameMetrics
from extensions import REDIS_URL

from repository.monitoramento_repository import MonitoramentoRepository
from services.visao.visao_geometria_mixin import VisaoGeometriaMixin
from services.visao.visao_desenho_mixin import VisaoDesenhoMixin
from services.visao.visao_postura_mixin import VisaoPosturaMixin
from services.estatisticas_service import EstatisticasService
from repository.setores_repository import SetoresRepository
from services.cameras_service import CamerasService
from services.alertas_service import AlertasService
from models.zonas import Zona

from worker.vision_pipeline import (
    aplicar_transformacoes,
    UltimoFrameContainer,
    LimitadorTempoChave,
    DisplayPublisher,
    CameraReader,
    CacheComTTL,
)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'best.pt')
MODEL_PATH_POSE = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'yolov8m-pose.pt')
logger = logging.getLogger(__name__)

def _obter_dimensao_env(nome_variavel: str, valor_padrao: int) -> int:
    partes = [int(p) for p in os.getenv(nome_variavel, valor_padrao).replace("x", ",").split(",") if p.strip()]
    return partes[0] if len(partes) == 1 else partes

class VisaoService(VisaoDesenhoMixin, VisaoPosturaMixin, VisaoGeometriaMixin):
    EPI_CLASSE_POR_LABEL = {
        'com_capacete': 'capacete',
        'sem_capacete': 'capacete',
        'com_chapeu': 'capacete',
        'com_luva': 'luva',
        'sem_luva': 'luva',
        'com_oculos': 'oculos',
        'com_oculos_normal': 'oculos',
        'sem_oculos': 'oculos',
        'com_mascara': 'mascara',
        'sem_mascara': 'mascara',
        'com_colete': 'colete',
        'sem_colete': 'colete'
    }

    BACKEND = os.getenv("VISION_BACKEND", "openvino").lower()
    DET_IMGSZ = _obter_dimensao_env("DET_IMGSZ", 640)
    POSE_IMGSZ = _obter_dimensao_env("POSE_IMGSZ", 480)

    DET_CONF = 0.3
    DET_IOU = 0.4
    DET_MIN_CONF = 0.5
    POSE_CONF = 0.5

    STREAM_FPS = float(os.getenv("STREAM_FPS", "30"))
    STREAM_LARGURA = int(os.getenv("STREAM_WIDTH", "960"))
    JPEG_QUALIDADE = int(os.getenv("JPEG_QUALITY", "75"))
    CAPTURA_MAX_FPS = float(os.getenv("CAPTURE_MAX_FPS", "0"))

    POSE_INTERVALO_ATIVO = float(os.getenv("POSE_ACTIVE_INTERVAL", "0.2"))
    POSE_INTERVALO_OCIOSO = float(os.getenv("POSE_IDLE_INTERVAL", "1.0"))
    POSE_TEMPO_OCIOSO = float(os.getenv("POSE_IDLE_AFTER", "3.0"))
    POSE_LIMITE_USO_CPU = float(os.getenv("POSE_MAX_DUTY", "0.35"))

    TRACK_FPS = {
        "det": int(os.getenv("TRACK_FPS", "15")),
        "pose": max(1, int(round(1.0 / float(os.getenv("POSE_ACTIVE_INTERVAL", "0.2")))))
    }

    def __init__(self, connection):
        self.connection = connection
        self.monitoramento_repository = MonitoramentoRepository(connection)
        self.estatisticas_service = EstatisticasService(connection)
        self.setores_repository = SetoresRepository(connection)
        self.alertas_service = AlertasService(connection)
        self.cameras_service = CamerasService(connection)

        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        self.profiler = StageProfiler("visao")

        self.ultimo_flush_stats = time.time()
        self.intervalo_flush_stats = 60  # Intervalo de flush em segundos
        
        self.modelo = None
        self.modelo_pose = None
        self.cap = None

        # Active Learning
        self.active_learning_dir = os.path.join(BASE_DIR, 'assets', 'modelo', 'active_learning')
        self.al_img_dir = os.path.join(self.active_learning_dir,  'dataset_captura', 'images')
        self.al_lbl_dir = os.path.join(self.active_learning_dir,  'dataset_captura', 'labels')
        self.flag_path = os.path.join(self.active_learning_dir, 'active_learning.flag')
        os.makedirs(self.al_img_dir, exist_ok=True)
        os.makedirs(self.al_lbl_dir, exist_ok=True)
        self._al_cooldown = {}
        self._active_learning_ativo = False
        self._proxima_verificacao_al = 0.0

        # Caches e ocorrências
        self._pool_alertas = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alertas_pool")
        self._limitador = LimitadorTempoChave()
        self._cache_setores = CacheComTTL(ttl=60.0)

        self._rastreadores = {}
        self._geometria_zonas = {}
        self._estado_pose = {}
        self._postura_inicio = {}
        self._postura_emitido = {}

        self._ultimo_log_erro = 0.0
        self._total_cameras = 1

    # region -------------------- Modelos e Conexões -------------------- #
    def _resolver_caminho_modelo(self, caminho_pt: str) -> str:
        if self.BACKEND != "pt":
            base = os.path.splitext(caminho_pt)[0]
            candidatos = {
                "openvino": base + "_openvino_model",
                "ncnn": base + "_ncnn_model",
                "onnx": base + ".onnx",
            }

            candidato = candidatos.get(self.BACKEND)

            if candidato and os.path.exists(candidato):
                return candidato

            print(f"⚠️ VISION_BACKEND={self.BACKEND}, mas '{candidato}' não existe. Usando PyTorch (.pt).")
        return caminho_pt
    
    def _inicializar_modelos(self):
        if self.modelo is not None and self.modelo_pose is not None:
            return

        caminho_det = self._resolver_caminho_modelo(MODEL_PATH)
        caminho_pose = self._resolver_caminho_modelo(MODEL_PATH_POSE)

        self.modelo = YOLO(caminho_det, task="detect")
        self.modelo_pose = YOLO(caminho_pose, task="pose")
        print(f"🧠 Modelos carregados: Detecção={os.path.basename(caminho_det)}, Pose={os.path.basename(caminho_pose)}")

        frame_teste = np.zeros((720, 1280, 3), dtype=np.uint8)
        for _ in range(2):
            self.modelo.predict(frame_teste, imgsz=self.DET_IMGSZ, verbose=False)
            self.modelo_pose.predict(frame_teste, imgsz=self.POSE_IMGSZ, verbose=False)

    def abrir_camera(self, camera_id: int):
        """
            Abre o stream de vídeo RTSP da câmera com ID especificado
            Se não encontrar RTSP ou falhar, faz fallback para webcam local.
        """
        ip = None
        try:
            # Busca os dados da câmera por ID
            camera = self.cameras_service.obter_camera_por_id(camera_id)

            if camera:
                # Pega o RTSP da câmera
                ip = camera.get('ip') if isinstance(camera, dict) else getattr(camera, 'ip', None)

        except Exception as e:
            print(f"❌ Erro ao obter RTSP da câmera {camera_id}: {e}")


        # Se tiver URL RTSP, abre via FFMPEG forçando TCP
        if ip:
            if ip.startswith("rtsp://"):
                print(f"🔗 Conectando ao RTSP da câmera {camera_id}: {ip}")

                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                    "rtsp_transport;tcp|stimeout;1000000|rw_timeout;1000000|fflags;nobuffer|flush_packets;1|max_delay;100000|buffer_size;1024000"
                )

                cap = cv2.VideoCapture(ip, cv2.CAP_FFMPEG)

                # Configura timeouts nativos do OpenCV caso a versão do build suporte
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if cap.isOpened():
                    self.cap = cap
                    return self.cap    
                cap.release()
            
            # Se a URL for uma webcam local, tenta abrir diretamente
            elif ip.lower().startswith("local-webcam"):
                try:
                    # Vai receber o índice da webcam local, ex: "local-webcam:0"
                    index = int(ip.split(":")[1])

                    backend = self.obter_plataforma_camera()

                    cap = cv2.VideoCapture(index, backend)

                    if cap.isOpened():
                        sucesso, _ = cap.read()

                        if sucesso:
                            print(f"✅ Webcam local conectada com sucesso no índice {index}")
                            self.cap = cap
                            return self.cap
                    cap.release()

                except Exception as e:
                    print(f"❌ Erro ao abrir webcam local para a câmera {camera_id}: {e}")

        print("❌ Nenhuma câmera disponível encontrada.")
        self.cap = None
        return None


    def obter_plataforma_camera(self):
        """
        Retorna o backend de captura de vídeo apropriado com base no sistema operacional.
        """
        sistema = platform.system()

        if sistema == "Windows":
            return cv2.CAP_DSHOW
        elif sistema == "Linux":
            return cv2.CAP_V4L2
        else:
            return cv2.CAP_ANY
    # endregion

    # region -------------------- Zonas e Cache -------------------- #
    def _zonas_de_monitoramento(self, id_camera: int) -> list[Zona]:
        """
        Retorna a lista de zonas de monitoramento para a câmera especificada.
        """
        try:
            self.connection.rollback()
        except Exception:
            pass

        zonas = self.monitoramento_repository.get_zonas_monitoradas_por_id_camera(id_camera)

        for zona in zonas:
            if not zona.epis_categoria:
                zona.epis_categoria = ['pessoa']
            else:
                zona.epis_categoria = [str(epi).strip().lower() for epi in zona.epis_categoria if epi]
        
        return zonas

    def _carregar_zonas(self, camera_id: int) -> list[Zona]:
        zonas = self._zonas_de_monitoramento(camera_id)
        self._geometria_zonas.pop(camera_id, None)  # Limpa cache de geometria para recarregar
        self._cache_setores.invalidar()

        for zona in zonas:
            try:
                self._obter_id_setor_da_zona(zona.id)
            except Exception:
                pass
        return zonas

    def _obter_geometria_zonas(self, camera_id: int, largura: int, altura: int, zonas):
        cache = self._geometria_zonas.get(camera_id)

        if cache is not None and cache[0] == (largura, altura) and cache[1] is zonas:
            return cache[2]

        geometria = [(zona, self.regiao_para_caixa(self.regiao_para_pixels(zona.regiao, largura, altura))) for zona in zonas]
        self._geometria_zonas[camera_id] = ((largura, altura), zonas, geometria)
        
        return geometria

    def _obter_id_setor_da_zona(self, zona_id):
        def carregar():
            setor = self.setores_repository.get_setor_por_id_zona(zona_id)
            return setor.id if setor else None

        return self._cache_setores.obter(zona_id, carregar)

    def _classe_epi_por_label(self, label: str) -> str | None:
        """ Retorna a classe de EPI correspondente ao rótulo fornecido, ou None se não houver correspondência. """
        if not label:
            return None
        return self.EPI_CLASSE_POR_LABEL.get(str(label).strip().lower())

    def _zona_requer_classe(self, categorias_permitidas: list[str] | None, classe: str, permitido: bool = False) -> bool:
        """ Verifica se a zona requer a classe especificada, considerando as categorias permitidas e se a detecção é de pessoa. """
        if classe == "pessoa" and permitido:
            return True

        if not categorias_permitidas:
            return False

        for categoria in categorias_permitidas:
            categoria_normalizada = self._classe_epi_por_label(categoria) or str(categoria).strip().lower()

            if categoria_normalizada == classe:
                return True
        return False
    # endregion

    # region -------------------- Tracking e Inferência -------------------- #
    def _obter_rastreador(self, tipo: str, camera_id: int):
        """ Obtém o rastreador para o tipo e câmera especificados. """
        chave = (tipo, camera_id)

        rastreador = self._rastreadores.get(chave)

        if rastreador is None:
            # Carrega a configuração do rastreador ByteTrack a partir do arquivo YAML
            import yaml
            from ultralytics.trackers.byte_tracker import BYTETracker
            from ultralytics.utils import IterableSimpleNamespace
            from ultralytics.utils.checks import check_yaml

            # Configurações do rastreador
            caminho_yaml = check_yaml("bytetrack.yaml")
            with open(caminho_yaml, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)

            fps = self.TRACK_FPS[tipo]
            config_dict['fps'] = fps
            config_dict['frame_rate'] = fps

            rastreador = BYTETracker(args=IterableSimpleNamespace(**config_dict))
            self._rastreadores[chave] = rastreador

        return rastreador


    def _predizer_com_rastreamento(self, modelo, tipo: str, camera_id: int, frame, imgsz: int, conf: float, iou=None):
        """ Executa a predição do modelo com rastreamento, retornando o resultado e as trilhas rastreadas."""
        parametros = dict(imgsz=imgsz, conf=conf, verbose=False)

        if iou is not None:
            parametros['iou'] = iou

        with self.profiler.etapa(f"{tipo}.predicao_total"):
            resultado = modelo.predict(frame, **parametros)[0]

        velocidades = getattr(resultado, 'speed', None) or {}
        for etapa_nome in ('preprocess', 'inference', 'postprocess'):
            if etapa_nome in velocidades:
                self.profiler.adicionar_tempo(f"{tipo}.{etapa_nome}", velocidades[etapa_nome])

        with self.profiler.etapa(f"{tipo}.rastreamento"):
            if resultado.boxes is None or len(resultado.boxes) == 0:
                trilhas = np.empty((0, 7), dtype=np.float32)
            else:
                rastreador = self._obter_rastreador(tipo, camera_id)
                trilhas = np.asarray(
                    rastreador.update(resultado.boxes.cpu().numpy(), frame),
                    dtype=np.float32
                )
                if trilhas.size == 0:
                    trilhas = np.empty((0, 7), dtype=np.float32)

                elif trilhas.ndim != 2 or trilhas.shape[1] < 7:
                    raise RuntimeError(
                        f"Retorno inesperado do BYTETracker (formato recebido: {trilhas.shape}). "
                        "Esperado pelo menos 7 colunas: [x1, y1, x2, y2, track_id, conf, cls]."
                    )

        return resultado, trilhas
    # endregion
    
    # region -------------------- Efeitos Colaterais e Alertas -------------------- #
    def _executar_em_segundo_plano(self, funcao, *args, **kwargs):
        """ Executa a função fornecida em uma thread de fundo, lidando com erros de banco de dados e logando falhas. """
        # Função interna que será executada na thread de fundo
        def tarefa():
            try:
                funcao(*args, **kwargs) # Executa a função com os argumentos fornecidos
            except psycopg2.Error as exc:
                try:
                    self.connection.rollback()
                except Exception:
                    pass
                # Loga o erro de banco de dados com o código SQLSTATE, se disponível
                logger.warning("Falha em banco na thread de fundo (SQLSTATE %s).", getattr(exc, 'pgcode', None))
            except Exception as exc:
                logger.warning("Falha em segundo plano: %s", exc)

        self._pool_alertas.submit(tarefa)

    def _registrar_alerta_epi_incorreto(self, monitoramento: Zona, evento: str, track_id: int, severidade: int = 1) -> None:
        if monitoramento.id_monitorar is None:
            return

        cache_chave = f"lock:alerta:epi:{monitoramento.id_monitorar}:{evento}:{track_id}"
        
        # Tenta adquirir o lock no Redis com expiração de 30 segundos. Se a chave já existir, não registra o alerta novamente.
        acquired = self.redis_client.set(cache_chave, "1", ex=30, nx=True)

        # Se a chave já existir, significa que um alerta recente já foi registrado para este monitoramento, evento e track_id
        trace_alert_candidate("epi", monitoramento.id_monitorar, monitoramento.id, evento, track_id, acquired)

        # Se não conseguiu adquirir o lock, retorna sem registrar o alerta
        if not acquired:
            return

        setor = self.setores_repository.get_setor_por_id_zona(monitoramento.id)
        if setor is None:
            return

        responsaveis = self.setores_repository.get_responsaveis_por_id_setor(setor.id)
        self.alertas_service.registrar_alertas_com_notificacao_unica(
            monitoramento=monitoramento,
            responsaveis=responsaveis,
            evento=evento,
            severidade=severidade,
        )

        alarme = self.monitoramento_repository.get_alarme_por_id_monitorar(monitoramento.id_monitorar)
        if alarme:
            enviar_comando(comando="DISPARAR", endereco_esp32=alarme['endereco'])


    def _disparar_alerta_epi(self, zona, evento: str, track_id: int, severidade: int) -> None:
        if zona.id_monitorar is None:
            return

        chave = ("epi", zona.id_monitorar, zona.id, evento, track_id)
        if not self._limitador.permitir(chave, ttl=30.0):
            return

        self._executar_em_segundo_plano(self._registrar_alerta_epi_incorreto, zona, evento, track_id, severidade)


    def _registrar_amostra_estatistica(self, id_setor: int, track_id: int, conforme: bool) -> None:
        """ Registra uma amostragem temporizada de estatística para o setor especificado no Redis. """
        if not id_setor or track_id == -1:
            return

        # Chave única de lock (cadeado) de cooldown (tempo de recarga) de 5 segundos para evitar duplicidade de amostras
        temporizador_chave = f"lock:stats:track:{id_setor}:{track_id}"

        # Se a chave já existir, significa que uma amostra recente já foi registrada para este track_id no setor
        if not self.redis_client.set(temporizador_chave, "1", ex=10, nx=True):
            return

        pipe = self.redis_client.pipeline()
        pipe.incr(f"stats:buffer:{id_setor}:total_deteccoes")
        pipe.incr(f"stats:buffer:{id_setor}:conformes" if conforme else f"stats:buffer:{id_setor}:nao_conformes")
        pipe.sadd(f"stats:setores_ativos", id_setor)
        pipe.execute()


    def _registrar_amostra_conformidade(self, id_setor: int, track_id: int, conforme: bool) -> None:
        """ Registra uma amostragem de conformidade para o setor especificado, com cooldown de 10 segundos para cada track_id. """
        if not id_setor or track_id == -1:
            return
        
        chave = ("estatisticas", id_setor, track_id)
        if not self._limitador.permitir(chave, ttl=10.0):
            return

        self._executar_em_segundo_plano(self._registrar_amostra_estatistica, id_setor, track_id, conforme)


    def _flush_estatisticas_para_banco(self, forcar: bool = False) -> None:
        """ Salva os contadores agregados no Redis na tabela estatisticas no PostgreSQL. """

        agora = time.time()

        # Se não for forçar o flush e o intervalo de flush ainda não passou, retorna sem fazer nada
        if not forcar and (agora - self.ultimo_flush_stats < self.intervalo_flush_stats):
            return

        self.ultimo_flush_stats = agora
        try:
            # Coleta todos os setores ativos que tiveram estatísticas registradas recentemente
            setores = self.redis_client.smembers("stats:setores_ativos")

            if not setores:
                return

            for setor_id_str in setores:
                setor_id = int(setor_id_str)

                # Coleta os valores dos contadores no Redis
                pipe = self.redis_client.pipeline()
                pipe.getset(f"stats:buffer:{setor_id}:total_deteccoes", 0)
                pipe.getset(f"stats:buffer:{setor_id}:conformes", 0)
                pipe.getset(f"stats:buffer:{setor_id}:nao_conformes", 0)
                total, conformes, nao_conformes = [int(valor or 0) for valor in pipe.execute()]

                # Se houver alguma detecção registrada, armazena as estatísticas no banco de dados
                if total > 0:
                    sucesso = self.estatisticas_service.armazenar_estatisticas(
                        id_setor=setor_id,
                        total_deteccoes=total,
                        total_conformes=conformes,
                        total_nao_conformes=nao_conformes
                    )

                    if not sucesso:
                        print(f"❌ Falha ao armazenar estatísticas para o setor {setor_id}: total={total}, conformes={conformes}, não conformes={nao_conformes}")

            # Após processar todos os setores, limpa a lista de setores ativos no Redis
            self.redis_client.delete("stats:setores_ativos")

        except Exception as e:
            print(f"❌ Erro ao coletar estatísticas do Redis para flush: {e}")


    def _monitorar_tempo_postura(
            self, camera_id: int, track_id: int, tipo_deteccao: str, motivo: str, ativo: bool,
            tempo_limite_segundos: int = 10, severidade: int = 1
    ) -> None:
        """ Garante que o alerta só seja disparado se a postura incorreta persistir por um tempo mínimo (tempo_limite_segundos). """

        if tipo_deteccao not in TIPOS_POSTURA:
            raise ValueError(f"tipo_deteccao '{tipo_deteccao}' inválido para postura.")

        chave = (camera_id, track_id, tipo_deteccao)
        agora = time.monotonic()

        # Chaves de controle no Redis para monitorar o tempo de postura e se o alerta já foi emitido
        if not ativo:
            self._postura_inicio.pop(chave, None)
            self._postura_emitido.pop(chave, None)
            return

        registro = self._postura_inicio.get(chave)
        if registro is None or (agora - registro[1]) > 60.0:
            registro = [agora, agora]
            self._postura_inicio[chave] = registro
        registro[1] = agora

        if self._postura_emitido.get(chave, 0.0) > agora:
            return

        tempo_decorrido = agora - registro[0]
        if tempo_decorrido >= tempo_limite_segundos:
            self._postura_emitido[chave] = agora + 45.0 # Marca como emitido com tempo de recarga (ex: 45s) para não disparar alertas repetidos
            self._executar_em_segundo_plano(
                self._emitir_alerta_postura, camera_id, track_id, tipo_deteccao, motivo, severidade, tempo_decorrido
            )

        if len(self._postura_inicio) > 2000:
            self._postura_inicio = {key: val for key, val in self._postura_inicio.items() if (agora - val[1]) < 60.0}

    def _emitir_alerta_postura(self, camera_id: int, track_id: int, tipo_deteccao: str, motivo: str, severidade: int, decorrido: float) -> None:
        setor = self.setores_repository.get_setor_por_id_camera(camera_id)

        if not setor:
            logger.warning(f"Setor não encontrado para câmera {camera_id}.")
            return

        responsaveis = self.setores_repository.get_responsaveis_por_id_setor(setor.id)
        sucesso = self.alertas_service.criar_alerta(
            monitoramento=None,
            id_usuario=responsaveis[0] if responsaveis else None,
            evento=f"Postura: {motivo}",
            severidade=severidade,
            destinatarios=responsaveis,
            tipo_deteccao=tipo_deteccao,
            id_camera=camera_id,
        )

        if sucesso:
            print(f"⚠️ Alerta emitido: {tipo_deteccao} contínua ({int(decorrido)}s) - Track ID: {track_id}")
    # endregion

    # region -------------------- Active Learning -------------------- #
    def _verificar_active_learning_ativo(self) -> bool:
        """ Verifica se o Active Learning está ativo lendo o arquivo de flag, com cache de 2 segundos para evitar leituras frequentes. """
        agora = time.monotonic()

        if agora >= self._proxima_verificacao_al:
            self._proxima_verificacao_al = agora + 2.0
            try:
                with open(self.flag_path, 'r') as f:
                    self._active_learning_ativo = f.read().strip() == "1"
            except OSError:
                self._active_learning_ativo = False

        return self._active_learning_ativo

    def _processar_active_learning(self, frame_limpo, boxes, img_shape: tuple[int, int]) -> None:
        """ Método para a regra de Active Learning e Amostragem de Incerteza. """
        agora = time.monotonic()
        img_altura, img_largura = img_shape
        
        # Verifica primeiro se existe algum objeto duvidoso na cena (confiança entre 0.3 e 0.7)
        tem_objeto_incerto = any(0.3 <= float(box.conf[0]) <= 0.7 for box in boxes)

        if not tem_objeto_incerto:
            return

        # Se houver objetos duvidosos, processa o Active Learning
        # Avalia o cooldown de disparo
        cache_chave = "al_uncertainty"
        ultimo_salvo = self._al_cooldown.get(cache_chave, 0)

        # Verifica se o cooldown ainda está ativo (5 segundos)
        if agora - ultimo_salvo <= 5:
            return  
        
        # Coleta os rótulos do frame
        yolo_anotacoes = []
        for box in boxes:
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            x_centro = ((x1 + x2) / 2) / img_largura
            y_centro = ((y1 + y2) / 2) / img_altura
            largura = (x2 - x1) / img_largura
            altura = (y2 - y1) / img_altura
            yolo_anotacoes.append(f"{cls} {x_centro:.6f} {y_centro:.6f} {largura:.6f} {altura:.6f} : {conf:.2f}")

        # Se houver anotações, salva o frame e as anotações em arquivos separados para Active Learning
        if yolo_anotacoes:
            self._al_cooldown[cache_chave] = agora
            timestamp = int(time.time() * 1000)
            img_filename = os.path.join(self.al_img_dir, f"frame_al_{timestamp}.jpg")
            lbl_filename = os.path.join(self.al_lbl_dir, f"frame_al_{timestamp}.txt")
            self._salvar_active_learning_async(frame_limpo, yolo_anotacoes, img_filename, lbl_filename)

    def _salvar_active_learning_async(self, frame_limpo, yolo_anotacoes, img_filename, lbl_filename):
        """ Salva as imagens e labels em uma thread separada para não travar o loop principal. """
        def salvar():
            try:
                cv2.imwrite(img_filename, frame_limpo)
                with open(lbl_filename, 'w') as f:
                    f.write("\n".join(yolo_anotacoes))
                print(f"📸 Frame salvo para Active Learning: {img_filename}")
            except Exception as e:
                print(f"❌ Erro ao salvar frame para Active Learning: {e}")

        threading.Thread(target=salvar, daemon=True).start()
    # endregion
    
    # region -------------------- Detecção e Estimativa de Pose -------------------- #
    def _detectar_objetos_frame(self, camera_id: int, frame, zonas) -> tuple[list[dict], dict[str, int], list[tuple]]:
        altura, largura = frame.shape[:2]
        deteccoes = []
        contagem_classes = defaultdict(int)
        overlay_caixas = []

        resultado, trilhas = self._predizer_com_rastreamento(
            self.modelo, "det", camera_id, frame, self.DET_IMGSZ, self.DET_CONF, self.DET_IOU
        )

        with self.profiler.etapa("det.regras_negocio"):
            if resultado.boxes is not None and len(resultado.boxes) > 0:
                self._processar_active_learning(frame, resultado.boxes, (altura, largura))

            geometria = self._obter_geometria_zonas(camera_id, largura, altura, self._zonas_de_monitoramento(camera_id))
            nomes_classes = self.modelo.names

            for linha in trilhas.tolist():
                x1, y1, x2, y2, tid, conf, cls = linha[:7]

                if conf < self.DET_MIN_CONF:
                    continue

                track_id = int(tid)
                coordenadas_xyxy = (int(x1), int(y1), int(x2), int(y2))
                nome_rotulo = nomes_classes[int(cls)].lower()
                classe_epi = self._classe_epi_por_label(nome_rotulo)
                nome_formatado = nome_rotulo.capitalize().replace("_", " ")
                zonas_do_objeto = []

                for zona, caixa_zona in geometria:
                    if not self._caixas_intersectam(coordenadas_xyxy, caixa_zona):
                        continue

                    if self._zona_requer_classe(zona.epis_categoria, classe_epi, zona.permitido):
                        zonas_do_objeto.append(zona.id)
                        id_setor = self._obter_id_setor_da_zona(zona.id)

                        if nome_rotulo.startswith("sem_"):
                            overlay_caixas.append(('box', coordenadas_xyxy, nome_formatado, 'vermelho'))
                            self._disparar_alerta_epi(zona, f"Sem EPI necessário: {classe_epi}", track_id, 2)
                            self._registrar_amostra_conformidade(id_setor, track_id, False)
                        
                        elif nome_rotulo.endswith("_chapeu"):
                            overlay_caixas.append(('box', coordenadas_xyxy, nome_formatado, 'amarelo'))
                            self._disparar_alerta_epi(zona, f"Equipamento inadequado: {classe_epi}", track_id, 1)
                            self._registrar_amostra_conformidade(id_setor, track_id, False)
                        
                        elif nome_rotulo.endswith("_normal"):
                            overlay_caixas.append(("box", coordenadas_xyxy, nome_formatado.replace("Normal", ""), "verde"))
                            self._registrar_amostra_conformidade(id_setor, track_id, True)
                        
                        else:
                            overlay_caixas.append(("box", coordenadas_xyxy, nome_formatado, "verde"))
                            self._registrar_amostra_conformidade(id_setor, track_id, True)
                    
                    if nome_rotulo == "pessoa":
                        if not self._zona_requer_classe(zona.epis_categoria, "pessoa", zona.permitido):
                            overlay_caixas.append(("box", coordenadas_xyxy, f"Pessoa ID: {track_id} (Zona restrita)", "amarelo"))
                            self._disparar_alerta_epi(zona, "Pessoa em zona restrita", track_id, 3)
                        else:
                            overlay_caixas.append(("box", coordenadas_xyxy, f"Pessoa ID: {track_id}", "branco"))
                
                contagem_classes[nome_rotulo] += 1
                for zona_id in zonas_do_objeto:
                    deteccoes.append({"id": track_id, "label": nome_rotulo, "confidence": conf, "zona": zona_id})

        return deteccoes, contagem_classes, overlay_caixas

    def _estimar_pose_frame(self, camera_id: int, frame) -> list[dict]:
        pessoas = []

        resultado, trilhas = self._predizer_com_rastreamento(
            self.modelo_pose, "pose", camera_id, frame, self.POSE_IMGSZ, self.POSE_CONF
        )

        with self.profiler.etapa("pose.regras_negocio"):
            if resultado.keypoints is None or len(trilhas) == 0:
                return pessoas

            keypoints_todas = resultado.keypoints.xy.cpu().numpy()
            for idx_linha, linha in enumerate(trilhas):
                indice_det = int(linha[7]) if len(linha) >= 8 else idx_linha
                track_id = int(linha[4])

                if indice_det >= len(keypoints_todas):
                    continue

                pontos = keypoints_todas[indice_det]
                if len(pontos) < 17:
                    continue

                ombro_esq, ombro_dir = pontos[5], pontos[6]
                quadril_esq, quadril_dir = pontos[11], pontos[12]
                joelho_esq, joelho_dir = pontos[13], pontos[14]
                tornozelo_esq, tornozelo_dir = pontos[15], pontos[16]

                cor_coluna = "ciano"
                coluna = None
                pontos_validos = all(p[0] > 0 and p[1] > 0 for p in (ombro_esq, ombro_dir, quadril_esq, quadril_dir))

                if not pontos_validos:
                    cor_coluna = "cinza"
                else:
                    ma_postura, motivo, pt_ombro, pt_quadril = self._avaliar_postura(
                        "tronco", ombro_esq=ombro_esq, ombro_dir=ombro_dir, quadril_esq=quadril_esq, quadril_dir=quadril_dir
                    )
                    if ma_postura:
                        cor_coluna = "vermelho"
                    coluna = (pt_ombro, pt_quadril)

                    self._monitorar_tempo_postura(
                        camera_id=camera_id, track_id=track_id, tipo_deteccao="postura_tronco",
                        motivo=motivo if ma_postura else "Postura normal", ativo=ma_postura,
                        tempo_limite_segundos=10, severidade=1
                    )

                    ma_rot, motivo_rot, _, _ = self._avaliar_postura(
                        "rotacao", ombro_esq=ombro_esq, ombro_dir=ombro_dir, quadril_esq=quadril_esq, quadril_dir=quadril_dir
                    )
                    self._monitorar_tempo_postura(
                        camera_id=camera_id, track_id=track_id, tipo_deteccao="postura_rotacao",
                        motivo=motivo_rot if ma_rot else "Sem rotacao excessiva", ativo=ma_rot,
                        tempo_limite_segundos=10, severidade=1
                    )

                    queda, motivo_queda, _, _ = self._avaliar_postura(
                        "queda", ombro_esq=ombro_esq, ombro_dir=ombro_dir, quadril_esq=quadril_esq, quadril_dir=quadril_dir,
                        joelho_esq=joelho_esq, joelho_dir=joelho_dir, tornozelo_esq=tornozelo_esq, tornozelo_dir=tornozelo_dir
                    )
                    self._monitorar_tempo_postura(
                        camera_id=camera_id, track_id=track_id, tipo_deteccao="queda",
                        motivo=motivo_queda if queda else "Em pé", ativo=queda,
                        tempo_limite_segundos=3, severidade=3
                    )

                pessoas.append({"pontos": pontos, "coluna": coluna, "cor": cor_coluna})

        return pessoas
    # endregion

    # region -------------------- Loop Principal -------------------- #
    def _processar_quadro_camera(self, camera_id: int, frame, zonas, overlay_anterior: dict | None):
        agora = time.monotonic()

        with self.profiler.etapa("total.deteccoes"):
            deteccoes, contagem_classes, overlay_det = self._detectar_objetos_frame(camera_id, frame, zonas)

        estado = self._estado_pose.setdefault(camera_id, {"ultima_execucao": 0.0, "ultima_pessoa": agora, "media_tempo": 0.0})
        if "pessoa" in contagem_classes:
            estado["ultima_pessoa"] = agora
        
        cenario_ocioso = (agora - estado["ultima_pessoa"]) > self.POSE_TEMPO_OCIOSO
        intervalo_base = self.POSE_INTERVALO_OCIOSO if cenario_ocioso else self.POSE_INTERVALO_ATIVO
        limite_cpu = max(0.05, self.POSE_LIMITE_USO_CPU)
        intervalo_calculado = max(intervalo_base, estado["media_tempo"] / limite_cpu)

        overlay_pose = overlay_anterior.get("pose", []) if overlay_anterior else []
        tempo_pose = overlay_anterior.get("pose_tempo", 0.0) if overlay_anterior else 0.0

        if agora - estado["ultima_execucao"] >= intervalo_calculado:
            estado["ultima_execucao"] = agora
            inicio_pose = time.perf_counter()

            with self.profiler.etapa("total.postura"):
                overlay_pose = self._estimar_pose_frame(camera_id, frame)

            duracao = time.perf_counter() - inicio_pose

            estado["media_tempo"] = duracao if estado["media_tempo"] == 0.0 else (0.7 * estado["media_tempo"] + 0.3 * duracao)

            tempo_pose = time.monotonic()

            if overlay_pose:
                estado["ultima_pessoa"] = tempo_pose

            self.profiler.marcar_evento(f"cam{camera_id}.pose_fps")
        
        overlay_consoliado = {
            "det": overlay_det,
            "det_tempo": time.monotonic(),
            "pose": overlay_pose,
            "pose_tempo": tempo_pose,
        }

        return deteccoes, contagem_classes, overlay_consoliado


    def run_batch_video_loop(
        self,
        cameras: list[int],
        frame_filas: dict,
        ultimos_resultados: dict[int, dict],
        parar_evento=None,
        recarregar_zonas_eventos=None,
        carimbos_espectadores=None,
    ):
        """
            Executa o loop de processamento em batch (lote) para múltiplas câmeras.
            Usa threads leves de leitura para evitar bloqueio por timeout de rede
            e processa a inferência de visão computacional agrupando os frames disponíveis.
        """
        cv2.setNumThreads(int(os.getenv("VISION_CV_THREADS", "2")))
        self._inicializar_modelos()
        self._total_cameras = len(cameras)
        evento_parada = parar_evento if parar_evento is not None else threading.Event()

        cache_transformacoes = CacheComTTL(ttl=5.0)

        def transformar(frame, camera_id):
            transformacao = cache_transformacoes.obter(camera_id, lambda: self.cameras_service.obter_transformacoes_camera(camera_id))
            return frame if not transformacao else aplicar_transformacoes(frame, *transformacao)

        zonas_por_camera: dict[int, list[Zona]] = {camera: self._carregar_zonas(camera) for camera in cameras}
        metricas = {camera: FrameMetrics() for camera in cameras}
        armazenamento_overlay = {}
        compartimentos = {camera: UltimoFrameContainer() for camera in cameras}
        ultimas_sequencias = defaultdict(int)
        ultimos_heartbeats = defaultdict(float)

        leitores = {}
        publicadores = []

        for camera_id in cameras:
            leitores[camera_id] = CameraReader(
                camera_id, self.abrir_camera, transformar, compartimentos[camera_id],
                evento_parada, self.profiler, fps_maximo=self.CAPTURA_MAX_FPS
            )
            leitores[camera_id].start()

            publicador = DisplayPublisher(
                camera_id, compartimentos[camera_id], armazenamento_overlay,
                frame_filas.get(camera_id) if frame_filas else None,
                carimbos_espectadores.get(camera_id) if carimbos_espectadores else None,
                evento_parada, self.desenhar_overlay, self.profiler,
                fps_alvo=self.STREAM_FPS, largura_stream=self.STREAM_LARGURA, qualidade_jpeg=self.JPEG_QUALIDADE
            )
            publicadores.append(publicador)
            publicador.start()

        try:
            while not evento_parada.is_set():
                if recarregar_zonas_eventos:
                    for camera_id in cameras:
                        evento = recarregar_zonas_eventos.get(camera_id)

                        if evento is not None and evento.is_set():
                            print(f"🔄 Recarregando zonas da câmera {camera_id} no processo de visão...")
                            zonas_por_camera[camera_id] = self._carregar_zonas(camera_id)
                            evento.clear()

                houve_trabalho = False
                for camera_id in cameras:
                    sequencia, pacote = compartimentos[camera_id].obter_atual()

                    if pacote is None or sequencia <= ultimas_sequencias[camera_id]:
                        continue

                    ultimas_sequencias[camera_id] = sequencia
                    frame, tempo_captura = pacote
                    houve_trabalho = True

                    inicio_processamento = time.perf_counter()
                    try:
                        deteccoes, contagem_classes, overlay = self._processar_quadro_camera(
                            camera_id, frame, zonas_por_camera[camera_id], armazenamento_overlay.get(camera_id)
                        )
                    except Exception as exc:
                        if time.monotonic() - self._ultimo_log_erro > 5.0:
                            self._ultimo_log_erro = time.monotonic()
                            print(f"❌ Erro ao processar quadro da câmera {camera_id}: {exc}")
                            traceback.print_exc()
                        continue

                    armazenamento_overlay[camera_id] = overlay
                    self.profiler.adicionar_tempo("total.quadro", (time.perf_counter() - inicio_processamento) * 1000.0)
                    self.profiler.adicionar_tempo("e2e.captura_ate_resultado", (time.monotonic() - tempo_captura) * 1000.0)
                    self.profiler.marcar_evento(f"cam{camera_id}.deteccoes_fps")

                    if ultimos_resultados is not None and camera_id in ultimos_resultados:
                        try:
                            medicao = metricas[camera_id].complete(tempo_captura, time.monotonic())
                            ultimos_resultados[camera_id].update({
                                "detections": deteccoes,
                                "class_count": dict(contagem_classes),
                                "result": dict(medicao, detections=deteccoes, class_count=dict(contagem_classes)),
                            })
                        except Exception:
                            pass

                agora = time.monotonic()
                for camera_id in cameras:
                    if (agora - ultimos_heartbeats[camera_id]) >= 1.0 and ultimos_resultados is not None and camera_id in ultimos_resultados:
                        ultimos_heartbeats[camera_id] = agora
                        try:
                            ultimos_resultados[camera_id].update({
                                "connected": leitores[camera_id].conectado,
                                "last_frame_time": leitores[camera_id].ultimo_frame_timestamp,
                            })
                        except Exception:
                            pass

                if not houve_trabalho:
                    time.sleep(0.002)

                self.profiler.emitir_relatorio()
                self._flush_estatisticas_para_banco()

        finally:
            print("🛑 Encerrando loop de visão em lote...")
            evento_parada.set()
            for thread in list(leitores.values()) + publicadores:
                thread.join(timeout=2.0)

            self._pool_alertas.shutdown(wait=False)
            self.profiler.emitir_relatorio(forcar=True)
            self._flush_estatisticas_para_banco(forcar=True)
    # endregion