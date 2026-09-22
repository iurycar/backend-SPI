from core.alerta_diagnostics import trace_alert_candidate
from core.tipo_deteccao import TIPOS_POSTURA
from core.vision_metrics import FrameMetrics
from collections import defaultdict
from extensions import REDIS_URL
from ultralytics import YOLO
import numpy as np
import threading
import platform
import psycopg2
import logging
import redis
import math
import time
import cv2
import os

from repository.monitoramento_repository import MonitoramentoRepository
from services.estatisticas_service import EstatisticasService
from repository.setores_repository import SetoresRepository
from services.cameras_service import CamerasService
from services.alertas_service import AlertasService
from models.zonas import Zona

from tasks.alarme_task import enviar_comando

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'best.pt')
MODEL_PATH_POSE = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'yolov8m-pose.pt')
logger = logging.getLogger(__name__)

class VisaoService:
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

    CORES = {
        'verde': (0, 255, 0),
        'vermelho': (0, 0, 255),
        'azul': (255, 0, 0),
        'amarelo': (0, 255, 255),
        'ciano': (255, 255, 0),
        'magenta': (255, 0, 255),
        'cinza': (120, 120, 120),
        'branco': (255, 255, 255),
    }

    # Paleta de cores mais moderna em BGR
    CORES_HUD = {
        'primaria': (255, 210, 0),     # Ciano
        'alerta': (0, 140, 255),       # Laranja/Âmbar
        'perigo': (70, 70, 255),       # Vermelho Coral
        'sucesso': (100, 230, 0),      # Verde Lima
        'escuro': (25, 25, 25),        # Quase preto para fundos
        'branco': (240, 240, 240),
        'cinza': (140, 140, 140)
    }


    def __init__(self, connection):
        self.connection = connection
        self.monitoramento_repository = MonitoramentoRepository(connection)
        self.estatisticas_service = EstatisticasService(connection)
        self.setores_repository = SetoresRepository(connection)
        self.alertas_service = AlertasService(connection)
        self.cameras_service = CamerasService(connection)

        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)

        self.ultimo_flush_stats = time.time()
        self.intervalo_flush_stats = 60  # Intervalo de flush em segundos

        self.last_results = []
        self.cap = None
        self.modelo = None
        self.modelo_pose = None

        self.active_learning_dir = os.path.join(BASE_DIR, 'assets', 'modelo', 'active_learning')
        self.al_img_dir = os.path.join(self.active_learning_dir,  'dataset_captura', 'images')
        self.al_lbl_dir = os.path.join(self.active_learning_dir,  'dataset_captura', 'labels')
        self.flag_path = os.path.join(self.active_learning_dir, 'active_learning.flag')
        
        os.makedirs(self.al_img_dir, exist_ok=True)
        os.makedirs(self.al_lbl_dir, exist_ok=True)
        self._al_cooldown = {}

        self._webcam_lock = threading.Lock()

    def _ensure_models_loaded(self):
        if self.modelo is None:
            self.modelo = YOLO(MODEL_PATH)
        if self.modelo_pose is None:
            self.modelo_pose = YOLO(MODEL_PATH_POSE)

    def open_camera(self, camera_id: int):
        """
            Abre o stream de vídeo RTSP da câmera com ID especificado
            Se não encontrar RTSP ou falhar, faz fallback para webcam local.
        """
        # RTSP = Real Time Streaming Protocol, usado para transmitir vídeo em tempo real de câmeras IP.
        # FFmpeg = Biblioteca de código aberto para processar vídeo e áudio, usada aqui para capturar o stream RTSP.
        # TCP = Transmission Control Protocol, garante entrega confiável de dados, usado aqui para reduzir perda de frames no stream RTSP.

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

                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
                    "rtsp_transport;tcp|"
                    "stimeout;3000000|"
                    "rw_timeout;3000000|"
                    "max_delay;500000|"
                    "buffer_size;2048000"
                )

                cap = cv2.VideoCapture(ip, cv2.CAP_FFMPEG)

                # Configura timeouts nativos do OpenCV caso a versão do build suporte
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if cap.isOpened():
                    self.cap = cap
                    return self.cap
                else:
                    cap.release()
            # Se a URL for uma webcam local, tenta abrir diretamente
            elif ip.lower().startswith("local-webcam"):
                try:
                    # Vai receber o índice da webcam local, ex: "local-webcam:0"
                    index = int(ip.split(":")[1])

                    backend = self.get_plataform_camera()

                    cap = cv2.VideoCapture(index, backend)

                    if cap.isOpened():
                        sucesso, _ = cap.read()

                        if sucesso:
                            print(f"✅ Webcam local conectada com sucesso no índice {index}")
                            cap.read()
                            self.cap = cap
                            return self.cap

                    cap.release()

                except Exception as e:
                    print(f"❌ Erro ao abrir webcam local para a câmera {camera_id}: {e}")

        print("❌ Nenhuma câmera disponível encontrada.")
        self.cap = None
        return None


    def get_plataform_camera(self):
        """
        Retorna o backend de captura de vídeo apropriado com base no sistema operacional.
        """

        system_name = platform.system()

        if system_name == "Windows":
            return cv2.CAP_DSHOW
        elif system_name == "Linux":
            return cv2.CAP_V4L2
        else:
            return cv2.CAP_ANY


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


    def _registrar_amostra_estatistica(self, id_setor: int, track_id: int, conforme: bool) -> None:
        """
            Registra uma amostragem temporizada de estatística para o setor especificado no Redis.
        """

        if not id_setor:
            return

        # Se o track_id for inválido, não registra a amostra
        if track_id == -1:
            return 

        # Chave única de lock (cadeado) de cooldown (tempo de recarga) de 5 segundos para evitar duplicidade de amostras
        temporizador_chave = f"lock:stats:track:{id_setor}:{track_id}"

        # Se a chave já existir, significa que uma amostra recente já foi registrada para este track_id no setor
        if not self.redis_client.set(temporizador_chave, "1", ex=10, nx=True):
            return

        pipe = self.redis_client.pipeline()
        pipe.incr(f"stats:buffer:{id_setor}:total_deteccoes")
        if conforme:
            pipe.incr(f"stats:buffer:{id_setor}:conformes")
        else:
            pipe.incr(f"stats:buffer:{id_setor}:nao_conformes")

        pipe.sadd(f"stats:setores_ativos", id_setor)
        pipe.execute()


    def _flush_estatisticas_para_banco(self, forcar: bool = False) -> None:
        """
            Salva os contadores agregados no Redis na tabela estatisticas no PostgreSQL
        """

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

                # Chaves para coleta de estatísticas no Redis
                chaves_total = f"stats:buffer:{setor_id}:total_deteccoes"
                chaves_conformes = f"stats:buffer:{setor_id}:conformes"
                chaves_nao_conformes = f"stats:buffer:{setor_id}:nao_conformes"

                # Coleta os valores dos contadores no Redis
                pipe = self.redis_client.pipeline()
                pipe.getset(chaves_total, 0)
                pipe.getset(chaves_conformes, 0)
                pipe.getset(chaves_nao_conformes, 0)
                resultados = pipe.execute()

                total = int(resultados[0] or 0)
                conformes = int(resultados[1] or 0)
                nao_conformes = int(resultados[2] or 0)

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


    def _armazenar_conformidade(self, camera_id: int, total_deteccoes: int, conformidades: int, nao_conformidades: int) -> None:
        """ Armazena as estatísticas de conformidade no banco de dados usando o serviço de estatísticas. """

        # TODO: Adicionar um registro no Redis
        # Exemplo: self.redis_client.set(f"conformidade:{camera_id}", f"{conformidades}:{nao_conformidades}")

        self.estatisticas_service.armazenar_estatisticas(camera_id, total_deteccoes, conformidades, nao_conformidades)


    def regiao_para_pixels(self, regiao, img_largura: int, img_altura: int) -> list[tuple[int, int]]:
        """
        Converte as coordenadas da região (seja normalizada 0.0..1.0 ou em pixels) para tuplas de inteiros de pixels na imagem.
        """
        if not regiao:
            return []

        # Verifica se as coordenadas na região estão normalizadas (<= 1.0)
        max_val = max(max(abs(float(p[0])), abs(float(p[1]))) for p in regiao)
        if max_val <= 1.0:
            return [
                (int(float(p[0]) * img_largura), int(float(p[1]) * img_altura))
                for p in regiao
            ]
        else:
            return [
                (int(float(p[0])), int(float(p[1])))
                for p in regiao
            ]

    def normalizar_regiao(self, regiao, img_largura: int, img_altura: int) -> list[list[float]]:
        """Garante que todos os pontos estão normalizados entre 0.0 e 1.0"""

        if not regiao:
            return []

        # Verifica se as coordenadas na região estão normalizadas (<= 1.0)
        max_val = max(
                    max(
                        abs(float(ponto[0])), 
                        abs(float(ponto[1]))
                    ) 
                for ponto in regiao
                )

        # Se todas as coordenadas já estão normalizadas, retorna a região como está
        if max_val <= 1.0:
            return [[float(ponto[0]), float(ponto[1])] for ponto in regiao]

        # Caso contrário, normaliza as coordenadas dividindo pelos tamanhos da imagem
        return [
            [round(float(ponto[0]) / img_largura, 4), round(float(ponto[1]) / img_altura, 4)]
            for ponto in regiao
        ] 


    def _caixas_intersectam(self, caixa1: tuple, caixa2: tuple) -> bool:
        """
        Verifica se duas caixas delimitadoras (caixa1 e caixa2) se intersectam.
        """
        x11, y11, x12, y12 = caixa1
        x21, y21, x22, y22 = caixa2

        return not (
            x12 < x21 or 
            x11 > x22 or 
            y12 < y21 or 
            y11 > y22
        )


    def regiao_para_caixa(self, regiao):
        """
        Converte uma região poligonal em uma caixa delimitadora (bounding box) representada por (x_min, y_min, x_max, y_max).
        """
        if not regiao:
            return 0, 0, 0, 0
        xs = [p[0] for p in regiao]
        ys = [p[1] for p in regiao]
        return min(xs), min(ys), max(xs), max(ys)


    def _classe_epi_por_label(self, label: str) -> str | None:
        if not label:
            return None
        return self.EPI_CLASSE_POR_LABEL.get(str(label).strip().lower())


    def _zona_requer_classe(self, categorias_permitidas: list[str] | None, classe: str, permitido: bool = False) -> bool:
        if classe == "pessoa" and permitido:
            return True

        if not categorias_permitidas:
            return False

        for categoria in categorias_permitidas:
            categoria_normalizada = self._classe_epi_por_label(categoria) or str(categoria).strip().lower()

            if categoria_normalizada == classe:
                return True

        return False


    def run_batch_video_loop(
            self, 
            cameras: list[int],
            frame_queues: dict,
            last_results: dict[int, dict], 
            stop_event=None, 
            reload_zones_events=None
        ):
        """
            Executa o loop de processamento em batch (lote) para múltiplas câmeras.
            Usa threads leves de leitura para evitar bloqueio por timeout de rede
            e processa a inferência de visão computacional agrupando os frames disponíveis.
        """
        self._ensure_models_loaded()

        zonas_por_camera: dict[int, list[Zona]] = {}
        
        # Dicionários de estado compartilhado entre threads/processos
        ultimos_frames = {}  # camera_id -> (sequence, frame, captured_at)
        sequencias = defaultdict(int)
        processados = defaultdict(int)
        metricas = {camera_id: FrameMetrics() for camera_id in cameras}
        locks_frames: dict[int, threading.Lock] = {}    
        cameras_ativas_status: dict[int, bool] = {}

        for camera_id in cameras:
            zonas_por_camera[camera_id] = self._zonas_de_monitoramento(camera_id)
            locks_frames[camera_id] = threading.Lock()
            cameras_ativas_status[camera_id] = False

        def thread_captura_camera(cam_id: int):
            cap = None
            proxima_tentativa = 0

            while not (stop_event is not None and stop_event.is_set()):
                tempo_atual = time.time()

                # Tenta abrir/reconectar
                if cap is None or not cap.isOpened():
                    if tempo_atual >= proxima_tentativa:
                        proxima_tentativa = tempo_atual + 5
                        cap = self.open_camera(cam_id)

                        if cap is None or not cap.isOpened():
                            cameras_ativas_status[cam_id] = False
                            if last_results is not None and cam_id in last_results:
                                info = last_results[cam_id]
                                info['connected'] = False
                                last_results[cam_id] = info
                            
                            if cap is not None:
                                cap.release()
                                cap = None
                            time.sleep(0.5)
                            continue
                    else:
                        time.sleep(0.2)
                        continue

                # Leitura do frame protegida
                sucesso, frame = cap.read()
                if not sucesso or frame is None or frame.size == 0:
                    cameras_ativas_status[cam_id] = False
                    if last_results is not None and cam_id in last_results:
                        info = last_results[cam_id]
                        info['connected'] = False
                        last_results[cam_id] = info

                    cap.release()
                    cap = None
                    proxima_tentativa = tempo_atual + 4
                    continue

                frame = self.aplicar_transformacoes_frame(frame, cam_id)

                with locks_frames[cam_id]:
                    sequencias[cam_id] += 1
                    ultimos_frames[cam_id] = (sequencias[cam_id], frame, time.monotonic())
                cameras_ativas_status[cam_id] = True
                
                if last_results is not None and cam_id in last_results:
                    info = last_results[cam_id]
                    info['connected'] = True
                    info['last_frame_time'] = time.time()
                    last_results[cam_id] = info

                time.sleep(0.01)

            if cap is not None:
                cap.release()
                print(f"🛑 Thread de captura da câmera {cam_id} finalizada e liberada.")

        # Inicia uma thread separada para cada câmera para captura contínua de frames
        threads = []
        for camera_id in cameras:
            thread = threading.Thread(target=thread_captura_camera, args=(camera_id,), daemon=True)
            thread.start()
            threads.append(thread)

        try:
            while not (stop_event is not None and stop_event.is_set()):
                tempo_atual = time.time()
                frames_lote: list[cv2.Mat] = []
                cams_processadas: list[int] = []

                pacotes_lote = []
                
                for camera_id in cameras:
                    # Verifica se não há nenhuma solicitação para recarregar zonas ou realizar reconexão
                    if reload_zones_events:
                        event = reload_zones_events.get(camera_id)

                        if event and event.is_set():
                            print(f"🔄 Recarregando zonas da câmera {camera_id} no processo de visão...")
                            zonas_por_camera[camera_id] = self._zonas_de_monitoramento(camera_id)
                            zonas_por_camera[camera_id] = self._zonas_de_monitoramento(camera_id)
                            event.clear()

                    if cameras_ativas_status.get(camera_id, False):
                        with locks_frames[camera_id]:
                            pacote = ultimos_frames.get(camera_id)

                            if pacote is not None and pacote[0] > processados[camera_id]:
                                sequence, frame, captured_at = pacote
                                pacotes_lote.append((camera_id, frame.copy(), captured_at, sequence))

                if not pacotes_lote:
                    time.sleep(0.01)
                    continue

                for pacote in pacotes_lote:
                    cams_processadas.append(pacote[0])
                    frames_lote.append(pacote[1])

                # Inferência YOLO em lotes (Deteção de objetos e avaliação de postura)
                try:
                    batch_detections, batch_count = self._batch_object_detection(frames_lote, cams_processadas, zonas_por_camera)
                    self._batch_pose_estimation(frames_lote, cams_processadas)
                except cv2.error as e:
                    print(f"❌ Erro de OpenCV durante a inferência em lote: {e}")
                    continue

                # Despacho dos resultados e frames estritamente emparelhados por camera_id
                for idx, (camera_id, frame_final, captured_at, sequence) in enumerate(pacotes_lote):
                    processados[camera_id] = sequence
                    detections = batch_detections[idx]
                    class_count = batch_count[idx]

                    # Atualiza os resultados compartilhados no Manager
                    if last_results is not None and camera_id in last_results:
                        info = last_results[camera_id]
                        info['detections'] = detections
                        info['class_count'] = dict(class_count)
                        measurement = metricas[camera_id].complete(captured_at, time.monotonic())
                        # One assignment publishes detections and their measurements together.
                        info['result'] = dict(measurement, detections=detections, class_count=dict(class_count))
                        last_results[camera_id] = info


                    """# >>>>>>>>>>>> PODE REMOVER ISSO, DEPOIS SOMENTE DEBUG <<<<<<<<<<<<
                    self._desenhar_hud_topo(frame_final, dict(class_count))
                    # ================================================================="""
                            
                    # Despacha o frame para a fila da respectiva câmera
                    frame_queue = frame_queues.get(camera_id) if frame_queues else None
                    if frame_queue is not None:
                        sucesso_enc, buffer = cv2.imencode('.jpg', frame_final)

                        if sucesso_enc:
                            if frame_queue.full():
                                try:
                                    frame_queue.get_nowait()  # Remove o frame antigo se a fila estiver cheia
                                except Exception:
                                    pass
                            try:
                                frame_queue.put(buffer.tobytes(), block=False)
                            except Exception:
                                pass

                # Flush periódico das estatísticas para o banco de dados
                self._flush_estatisticas_para_banco()
        finally:
            print("🛑 Encerrando loop de visão em lote...")
            self._flush_estatisticas_para_banco(forcar=True)


    def get_last_results(self):
        return self.last_results


    def aplicar_transformacoes_frame(
            self,
            frame: np.ndarray,
            camera_id: int
    ) -> np.ndarray:
        """
        Aplica rotação ortogonal e/ou espelhamento ao frame de uma câmera específica.

        :param frame: Imagem capturada (matriz numpy/cv2.Mat).
        :param camera_id: ID da câmera para rastreabilidade de logs.
        :param rotacao: Graus de rotação no sentido horário (90, 180, 270 ou 0/None).
        :param espelhar_horizontal: True para espelhar horizontalmente (flip eixo Y).
        :param espelhar_vertical: True para espelhar verticalmente (flip eixo X).
        :return: Frame processado.
        """
        if frame is None or frame.size == 0:
            return frame

        frame_processado = frame

        # Tratamento seguro contra retorno None do serviço/banco
        transformacoes = self.cameras_service.obter_transformacoes_camera(camera_id)
        if not transformacoes:
            return frame_processado

        rotacao, espelhar_horizontal, espelhar_vertical = transformacoes

        # 1. Rotação Ortogonal (cv2.rotate é O(1) em memória, sem interpolação afim)
        if rotacao in (90, -270):
            frame_processado = cv2.rotate(frame_processado, cv2.ROTATE_90_CLOCKWISE)
        elif rotacao in (180, -180):
            frame_processado = cv2.rotate(frame_processado, cv2.ROTATE_180)
        elif rotacao in (270, -90):
            frame_processado = cv2.rotate(frame_processado, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif rotacao not in (0, None):
            # Fallback para ângulos não múltiplos de 90° usando matriz afim
            altura, largura = frame_processado.shape[:2]
            centro = (largura // 2, altura // 2)
            matriz = cv2.getRotationMatrix2D(centro, -rotacao, 1.0)
            frame_processado = cv2.warpAffine(frame_processado, matriz, (largura, altura))

        # 2. Espelhamento (Flip)
        # cv2.flip: 1 = horizontal, 0 = vertical, -1 = ambos
        if espelhar_horizontal and espelhar_vertical:
            frame_processado = cv2.flip(frame_processado, -1)
        elif espelhar_horizontal:
            frame_processado = cv2.flip(frame_processado, 1)
        elif espelhar_vertical:
            frame_processado = cv2.flip(frame_processado, 0)

        return frame_processado


    def _processar_active_learning(self, frame_limpo, boxes, img_shape):
        """
        Método para a regra de Active Learning e Amostragem de Incerteza.
        """
        
        if not os.path.exists(self.flag_path):
            return
        
        with open(self.flag_path, 'r') as f:
            flag_value = f.read().strip()

        if flag_value != '1':
            return

        agora = time.monotonic()
        img_altura, img_largura = img_shape
        
        # Verifica primeiro se existe algum objeto duvidoso na cena (confiança entre 0.3 e 0.7)
        tem_objeto_incerto = False

        for box in boxes:
            conf = float(box.conf[0])

            if 0.3 <= conf <= 0.7:
                tem_objeto_incerto = True
                break

        if not tem_objeto_incerto:
            return  # Nenhuma incerteza na cena: descarta o processamento

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
            xyxy = box.xyxy[0].cpu().numpy().astype(int)

            x1, y1, x2, y2 = xyxy
            x_centro = ((x1 + x2) / 2) / img_largura
            y_centro = ((y1 + y2) / 2) / img_altura
            largura = (x2 - x1) / img_largura
            altura = (y2 - y1) / img_altura

            yolo_anotacoes.append(f"{cls} {x_centro:.6f} {y_centro:.6f} {largura:.6f} {altura:.6f} : {conf:.2f}")

        # Dispara o salvamento e atualiza o cooldown
        if len(yolo_anotacoes) > 0:
            self._al_cooldown[cache_chave] = agora
            timestamp = int(time.time() * 1000)
            img_filename = os.path.join(self.al_img_dir, f"frame_al_{timestamp}.jpg")
            lbl_filename = os.path.join(self.al_lbl_dir, f"frame_al_{timestamp}.txt")
            
            self._salvar_active_learning_async(frame_limpo, yolo_anotacoes, img_filename, lbl_filename)
        

    def _batch_object_detection(self, frames: list, cam_ids: list[int], zonas_por_camera: dict[int, list[Zona]]) -> tuple[list[list[dict]], list[defaultdict]]:
        self._ensure_models_loaded()

        if not frames:
            return [], []

        batch_detections = []
        batch_class_count = []

        for idx, frame in enumerate(frames):
            cam_id = cam_ids[idx]
            zonas_configuradas = zonas_por_camera.get(cam_id, [])

            detections = []
            class_count = defaultdict(int)        
            img_altura, img_largura = frame.shape[:2]
            frame_limpo = frame.copy()

            # Rastreamento individual por frame para evitar colisão entre câmeras distintas
            try:
                results = self.modelo.track(frame, persist=True, conf=0.3, iou=0.4, tracker="bytetrack.yaml", verbose=False)
                result = results[0] if results else None
            except Exception as e:
                logger.warning(f"Erro no tracking da câmera {cam_id}: {e}")
                result = None

            if result is not None and result.boxes is not None:
                self._processar_active_learning(frame_limpo, result.boxes, (img_altura, img_largura))

                for box in result.boxes:
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])

                    if conf >= 0.5:
                        track_id = int(box.id[0]) if box.id is not None else -1
                        label_name = self.modelo.names[cls].lower()

                        zonas_do_objeto = []

                        for monitoramento in zonas_configuradas:
                            regiao_px = self.regiao_para_pixels(monitoramento.regiao, img_largura, img_altura)
                            if self._caixas_intersectam(xyxy, self.regiao_para_caixa(regiao_px)):

                                if self._zona_requer_classe(monitoramento.epis_categoria, self._classe_epi_por_label(label_name), monitoramento.permitido):
                                    zonas_do_objeto.append(monitoramento.id)

                                    setor = self.setores_repository.get_setor_por_id_zona(monitoramento.id)
                                    if setor:
                                        id_setor = setor.id
                                    else:
                                        id_setor = None

                                    if label_name.startswith("sem_"):
                                        self._desenhar_caixa_delimitadora(frame, xyxy, f"{label_name.capitalize().replace('_', ' ')}", self.CORES.get('vermelho', (0, 0, 255)))
                                        self._registrar_alerta_epi_incorreto(monitoramento, f"Sem EPI necessário: {self._classe_epi_por_label(label_name)}", track_id, severidade=2)

                                        if id_setor:
                                            self._registrar_amostra_estatistica(id_setor, track_id, conforme=False)
                                    else:
                                        if label_name.endswith("_normal"):
                                            self._desenhar_caixa_delimitadora(frame, xyxy, f"{label_name.capitalize().replace('_', ' ')}", self.CORES.get('amarelo', (0, 255, 255)))
                                            self._registrar_alerta_epi_incorreto(monitoramento, f"Equipamento inadequado: {self._classe_epi_por_label(label_name)}", track_id, severidade=1)

                                            if id_setor:
                                                self._registrar_amostra_estatistica(id_setor, track_id, conforme=False)
                                        else:
                                            self._desenhar_caixa_delimitadora(frame, xyxy, f"{label_name.capitalize().replace('_', ' ')}", self.CORES.get('verde', (0, 255, 255)))

                                            if id_setor:
                                                self._registrar_amostra_estatistica(id_setor, track_id, conforme=True)

                                if label_name == "pessoa" and not self._zona_requer_classe(monitoramento.epis_categoria, "pessoa", monitoramento.permitido):
                                    self._desenhar_caixa_delimitadora(frame, xyxy, f"{label_name.capitalize()} ID:{track_id} (Zona Restrita)", self.CORES.get('vermelho', (0, 0, 255)))
                                    self._registrar_alerta_epi_incorreto(monitoramento, "Pessoa em zona restrita", track_id, severidade=3)
                                elif label_name == "pessoa":
                                    self._desenhar_caixa_delimitadora(frame, xyxy, f"{label_name.capitalize()} ID:{track_id}", self.CORES.get('branco', (0, 255, 0)))
                        
                        class_count[label_name] += 1

                        for z_id in zonas_do_objeto:
                            detections.append({
                                "id": track_id,
                                "label": label_name,
                                "confidence": conf,
                                "zona": z_id
                            })

            batch_detections.append(detections)
            batch_class_count.append(class_count)

        return batch_detections, batch_class_count

    def _salvar_active_learning_async(self, frame_limpo, yolo_anotacoes, img_filename, lbl_filename):
        """
        Salva as imagens e labels em uma thread separada para não travar o loop principal.
        """

        def salvar():
            try:
                cv2.imwrite(img_filename, frame_limpo)
                with open(lbl_filename, 'w') as f:
                    f.write("\n".join(yolo_anotacoes))
                print(f"📸 Frame salvo para Active Learning: {img_filename}")
            except Exception as e:
                print(f"❌ Erro ao salvar frame para Active Learning: {e}")

        threading.Thread(target=salvar, daemon=True).start()

    def _registrar_alerta_epi_incorreto(self, monitoramento: Zona, evento: str, track_id: int, severidade: int = 1) -> None:
        """
        Registra um alerta, evitando duplicidade por um curto período.
        """

        if monitoramento.id_monitorar is None:
            return

        # Chave única de lock (cadeado) de cooldown (tempo de recarga) de 30 segundos para evitar alertas duplicados
        cache_chave = f"lock:alerta:epi:{monitoramento.id_monitorar}:{evento}:{track_id}"

        # Se a chave já existir, significa que um alerta recente já foi registrado para este evento e track_id
        acquired = self.redis_client.set(cache_chave, "1", ex=30, nx=True)
        trace_alert_candidate('epi', monitoramento.id_camera, monitoramento.id,
                              evento, track_id, acquired)
        if not acquired:
            return # Já existe um alerta recente para este evento e track_id

        setor = self.setores_repository.get_setor_por_id_zona(monitoramento.id)

        if setor is None:
            return

        responsaveis = self.setores_repository.get_responsaveis_por_setor(setor.id)

        self.alertas_service.registrar_alertas_com_notificacao_unica(
            monitoramento=monitoramento, 
            responsaveis=responsaveis,
            evento=evento,
            severidade=severidade
        )

        alarme = self.monitoramento_repository.get_alarme_por_id_monitorar(monitoramento.id_monitorar)

        if not alarme:
            return

        enviar_comando(comando="DISPARAR", endereco_esp32=alarme['endereco'])

    def _avaliar_postura(self, metodo, **kargs):
        """
            Avalia a postura combinando o ângulo de inclinação (visão lateral) 
            e a proporção do tronco (visão frontal).
        """

        is_ma_postura: bool = False
        motivo: str = ""

        # =============
        # Método de cálculo do ângulo de inclinação (maior que 30 graus é considerado má postura)
        # =============
        if metodo == "tronco":
            ombro_esq: tuple[float, float] = kargs.get('ombro_esq')
            ombro_dir: tuple[float, float] = kargs.get('ombro_dir')
            quadril_esq: tuple[float, float] = kargs.get('quadril_esq')
            quadril_dir: tuple[float, float] = kargs.get('quadril_dir')

            if ombro_esq is None or ombro_dir is None or quadril_esq is None or quadril_dir is None:
                return is_ma_postura, motivo, (0, 0), (0, 0)

            # Calcula os pontos médios dos ombros e quadris
            pt_ombro: tuple[float, float] = ((ombro_esq[0] + ombro_dir[0]) / 2, (ombro_esq[1] + ombro_dir[1]) / 2)
            pt_quadril: tuple[float, float] = ((quadril_esq[0] + quadril_dir[0]) / 2, (quadril_esq[1] + quadril_dir[1]) / 2)

            # Calcula o ângulo de inclinação do tronco usando a função atan2
            dx: float = pt_ombro[0] - pt_quadril[0]
            dy: float = pt_quadril[1] - pt_ombro[1]
            angulo: float = math.degrees(math.atan2(abs(dx), abs(dy)))
            
            # Calcula a largura dos ombros usando a distância Euclidiana
            largura_ombros: float = math.dist(ombro_esq, ombro_dir)
            
            # Distância Euclidiana entre ombro e quadril (altura aparente do tronco)
            altura_tronco: float = math.dist(pt_ombro, pt_quadril)
            
            # Evitar divisão por zero
            largura_ombros: float = max(largura_ombros, 1) 
            
            # Calcula a proporção
            razao_tronco: float = altura_tronco / largura_ombros
            
            # Avaliação Híbrida
            # Ajuste estes limites de acordo com a altura e ângulo real da sua câmera na fábrica!
            LIMITE_ANGULO = 30 # graus
            LIMITE_RAZAO_FRONTAL = 1.1 # Se a altura do tronco for quase igual à largura dos ombros
            
            if angulo > LIMITE_ANGULO:
                is_ma_postura = True
                motivo = f"Inclinacao Excessiva do Tronco."
            elif razao_tronco < LIMITE_RAZAO_FRONTAL:
                is_ma_postura = True
                motivo = f"Inclinacao Excessiva do Tronco."

            return is_ma_postura, motivo, (int(pt_ombro[0]), int(pt_ombro[1])), (int(pt_quadril[0]), int(pt_quadril[1]))

        # ==============
        # Método de cálculo para rotação excessiva do tronco
        # ==============
        elif metodo == "rotacao":
            ombro_esq: tuple[float, float] = kargs.get('ombro_esq')
            ombro_dir: tuple[float, float] = kargs.get('ombro_dir')
            quadril_esq: tuple[float, float] = kargs.get('quadril_esq')
            quadril_dir: tuple[float, float] = kargs.get('quadril_dir')

            if ombro_esq is None or ombro_dir is None or quadril_esq is None or quadril_dir is None:
                return is_ma_postura, motivo, (0, 0), (0, 0)

            # Calcula a inclinação da linha dos ombros
            dx_ombros = ombro_dir[0] - ombro_esq[0]
            dy_ombros = ombro_dir[1] - ombro_esq[1]
            angulo_ombros = math.degrees(math.atan2(dy_ombros, dx_ombros))

            # Calcula a inclinação da linha dos quadris
            dx_quadris = quadril_dir[0] - quadril_esq[0]
            dy_quadris = quadril_dir[1] - quadril_esq[1]
            angulo_quadris = math.degrees(math.atan2(dy_quadris, dx_quadris))

            # A torção é a diferença absoluta entre os dois ângulos
            diferenca_rotacao = abs(angulo_ombros - angulo_quadris)

            # Normaliza para garantir que o ângulo seja o menor caminho (0 a 180)
            if diferenca_rotacao > 180:
                diferenca_rotacao = 360 - diferenca_rotacao

            # Limite de torção (ajuste conforme necessário)
            LIMITE_TORCAO = 30 # graus

            if diferenca_rotacao > LIMITE_TORCAO:
                is_ma_postura = True
                motivo = f"Rotação/Torção Excessiva."

            return is_ma_postura, motivo, (int(ombro_esq[0]), int(ombro_esq[1])), (int(quadril_esq[0]), int(quadril_esq[1]))

        # ==============
        # Método de cálculo para indivíduo caído no chão
        # ==============
        elif metodo == "queda":
            ombro_esq: tuple[float, float] = kargs.get('ombro_esq')
            ombro_dir: tuple[float, float] = kargs.get('ombro_dir')
            quadril_esq: tuple[float, float] = kargs.get('quadril_esq')
            quadril_dir: tuple[float, float] = kargs.get('quadril_dir')

            if ombro_esq is None or ombro_dir is None or quadril_esq is None or quadril_dir is None:
                return is_ma_postura, motivo, (0, 0), (0, 0)

            # Calcula as extremidades (bounding box) dos pontos do tronco
            min_x = min(ombro_esq[0], ombro_dir[0], quadril_esq[0], quadril_dir[0])
            max_x = max(ombro_esq[0], ombro_dir[0], quadril_esq[0], quadril_dir[0])
            min_y = min(ombro_esq[1], ombro_dir[1], quadril_esq[1], quadril_dir[1])
            max_y = max(ombro_esq[1], ombro_dir[1], quadril_esq[1], quadril_dir[1])

            largura = max_x - min_x
            altura = max_y - min_y

            # Evita divisão por zero
            altura = max(altura, 1)

            # Calcula a proporção geométrica da pessoa (Largura / Altura)
            proporcao = largura / altura

            # Se a largura for 20% maior que a altura do tronco, é muito provável que esteja no chão
            LIMITE_QUEDA = 1.2 

            if proporcao > LIMITE_QUEDA:
                is_ma_postura = True
                motivo = f"Pessoa caída no chão."

            # Calcula o ponto central do corpo para exibir a mensagem corretamente
            centro_x = int((min_x + max_x) / 2)
            centro_y = int((min_y + max_y) / 2)

            return is_ma_postura, motivo, (centro_x, centro_y), (centro_x, centro_y)


    def _batch_pose_estimation(self, frames: list, cameras_id: list[int]) -> None:
        """
        Implementa a lógica de estimativa de pose, desenha o esqueleto e 
        calcula a inclinação do tronco para gerar alertas de má postura.
        """
        self._ensure_models_loaded()

        if not frames:
            return
        
        results = self.modelo_pose.track(frames, persist=True, conf=0.5, tracker="bytetrack.yaml", verbose=False)

        esqueleto_conexoes = [
            (0, 1), (0, 2), (1, 3), (2, 4),            
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),   
            (5, 11), (6, 12), (11, 12),                
            (11, 13), (13, 15), (12, 14), (14, 16)     
        ]

        for i, result in enumerate(results):
            frame = frames[i]
            camera_id = cameras_id[i]
            
            if result.keypoints is not None and len(result.keypoints) > 0:
                keypoints_list = result.keypoints.xy.cpu().numpy()
                
                # Tenta pegar os IDs das pessoas rastreadas
                track_ids = result.boxes.id.int().cpu().tolist() if result.boxes and result.boxes.id is not None else [-1] * len(keypoints_list)

                # Itera sobre cada conjunto de keypoints (uma pessoa) e desenha os pontos e linhas do esqueleto
                for idx, individual in enumerate(keypoints_list):
                    if len(individual) < 17:
                        continue

                    track_id = track_ids[idx]

                    # Desenhar pontos e linhas (Seu código original mantido)
                    for ponto in individual:
                        x, y = int(ponto[0]), int(ponto[1])
                        if x > 0 and y > 0:
                            # Keypoints com centro preenchido e contorno
                            cv2.circle(frame, (x, y), 4, (0, 255, 180), -1, cv2.LINE_AA)
                            cv2.circle(frame, (x, y), 5, (20, 20, 20), 1, cv2.LINE_AA)

                    # Desenhar as conexões do esqueleto
                    for p1, p2 in esqueleto_conexoes:
                        x1, y1 = int(individual[p1][0]), int(individual[p1][1])
                        x2, y2 = int(individual[p2][0]), int(individual[p2][1])
                        if (x1 > 0 and y1 > 0) and (x2 > 0 and y2 > 0):
                            cv2.line(frame, (x1, y1), (x2, y2), (255, 180, 0), 2, cv2.LINE_AA)

                    # Pega os pontos dos ombros e quadris
                    ombro_esq, ombro_dir = individual[5], individual[6]
                    quadril_esq, quadril_dir = individual[11], individual[12]

                    cor_coluna = self.CORES.get('ciano', (0, 255, 255))
                    pontos_validos = True

                    # 1. Primeiro apenas verifica se TODOS os pontos são válidos
                    for p in [ombro_esq, ombro_dir, quadril_esq, quadril_dir]:
                        if p[0] <= 0 or p[1] <= 0:
                            pontos_validos = False
                            break

                    # 2. Se houver algum ponto inválido (ex: fora da tela), não avalia a postura
                    if not pontos_validos:
                        cor_coluna = self.CORES.get('cinza', (120, 120, 120))
                    
                    # 3. Se todos os 4 pontos são válidos, avalia a postura uma ÚNICA vez
                    else:
                        # --- AVALIAÇÃO DO TRONCO ---
                        is_ma_postura, motivo, pt_ombro, pt_quadril = self._avaliar_postura(
                            "tronco", 
                            ombro_esq=ombro_esq, ombro_dir=ombro_dir, 
                            quadril_esq=quadril_esq, quadril_dir=quadril_dir
                        )
                        
                        if is_ma_postura:
                            cor_coluna = self.CORES.get('vermelho', (0, 0, 255))    
                        cv2.line(frame, pt_ombro, pt_quadril, cor_coluna, 4, cv2.LINE_AA)

                        if track_id != -1:
                            self._monitorar_tempo_postura(
                                camera_id=camera_id,
                                track_id=track_id, 
                                tipo_deteccao='postura_tronco',
                                motivo=motivo if is_ma_postura else "Postura normal",
                                ativo=is_ma_postura,
                                tempo_limite_segundos=10,
                                severidade=1
                            )                        

                        # --- AVALIAÇÃO DA ROTAÇÃO ---
                        is_ma_postura_rotacao, motivo_rotacao, _, _ = self._avaliar_postura(
                            "rotacao", 
                            ombro_esq=ombro_esq, ombro_dir=ombro_dir, 
                            quadril_esq=quadril_esq, quadril_dir=quadril_dir
                        )
                        
                        if track_id != -1:
                            self._monitorar_tempo_postura(
                                camera_id=camera_id,
                                track_id=track_id, 
                                tipo_deteccao='postura_rotacao',
                                motivo=motivo_rotacao if is_ma_postura_rotacao else "Sem rotacao excessiva",
                                ativo=is_ma_postura_rotacao,
                                tempo_limite_segundos=10,
                                severidade=1
                            )

                        # --- AVALIAÇÃO DE QUEDA ---
                        is_caido, motivo_queda, _, _ = self._avaliar_postura(
                            "queda", 
                            ombro_esq=ombro_esq, ombro_dir=ombro_dir, 
                            quadril_esq=quadril_esq, quadril_dir=quadril_dir
                        )

                        if track_id != -1:
                            self._monitorar_tempo_postura(
                                camera_id=camera_id,
                                track_id=track_id,
                                tipo_deteccao='queda',
                                motivo=motivo_queda if is_caido else "Em pé",
                                ativo=is_caido,
                                tempo_limite_segundos=3,
                                severidade=3
                            )


    def _monitorar_tempo_postura(self,
                                 camera_id: int,
                                 track_id: int,
                                 tipo_deteccao: str,
                                 motivo: str,
                                 ativo: bool,
                                 tempo_limite_segundos: int = 10,
                                 severidade: int = 1
                                ) -> None:
        """
            Garante que o alerta só seja disparado se a postura incorreta persistir por um tempo mínimo (tempo_limite_segundos).
        """

        if tipo_deteccao not in TIPOS_POSTURA:
            raise ValueError(f"tipo_deteccao '{tipo_deteccao}' inválido para postura.")

        chave_inicio = f"postura:inicio:{camera_id}:{track_id}:{tipo_deteccao}"
        chave_alerta_emitido = f"postura:emitido:{camera_id}:{track_id}:{tipo_deteccao}"

        agora = time.time()

        # Se a postura não está mais ativa, remove o registro de início e o alerta emitido
        if not ativo:
            self.redis_client.delete(chave_inicio)
            self.redis_client.delete(chave_alerta_emitido)
            return

        # Se a postura está ativa, registra o tempo de início se ainda não existir
        self.redis_client.set(chave_inicio, str(agora), nx=True, ex=60)

        # Se a chave de início já existia, atualiza o tempo de expiração para 60 segundos
        self.redis_client.expire(chave_inicio, 60)

        # Se o alerta já foi emitido recentemente, não faz nada
        if self.redis_client.get(chave_alerta_emitido):
            return

        inicio_timestamp_str = self.redis_client.get(chave_inicio)
        if not inicio_timestamp_str:
            return

        tempo_decorrido = agora - float(inicio_timestamp_str)

        print(f"⏱️ Tempo de postura '{tipo_deteccao}' para câmera {camera_id}, track ID {track_id}: {int(tempo_decorrido)}s (limite: {tempo_limite_segundos}s)")

        if tempo_decorrido >= tempo_limite_segundos:
            # Marca como emitido com tempo de recarga (ex: 45s) para não disparar alertas repetidos
            self.redis_client.set(chave_alerta_emitido, "1", ex=45)

            try:
                setor = self.setores_repository.get_setor_por_id_camera(camera_id)

                if not setor:
                    logger.warning(f"Setor não encontrado para a câmera {camera_id}. Não é possível registrar alerta de postura.")
                    return

                responsaveis = self.setores_repository.get_responsaveis_por_setor(setor.id)

                sucesso = self.alertas_service.criar_alerta(
                    monitoramento=None,
                    id_usuario=responsaveis[0] if responsaveis else None,
                    evento=f"Má postura detectada: {motivo}",
                    severidade=severidade,
                    destinatarios=responsaveis,
                    tipo_deteccao=tipo_deteccao,
                    id_camera=camera_id
                )

                if sucesso:
                    print(f"⚠️ Alerta emitido: {tipo_deteccao} contínua ({int(tempo_decorrido)}s) - Track ID: {track_id}")

            except psycopg2.Error as exc:
                self.connection.rollback()
                logger.warning("Falha ao registrar postura da câmera %s (SQLSTATE %s).", camera_id, exc.pgcode)
            except (ValueError, redis.exceptions.RedisError) as exc:
                logger.warning('Falha ao registrar/notificar postura da câmera %s: %s.', camera_id, exc)




    # ==================================================
    # Funções para embelezar o UI do vídeo, desenhando zonas, caixas e cantos estilizados
    # ==================================================
    def _desenhar_cantos(self, frame, x1, y1, x2, y2, cor, espessura=2, comprimento=12):
        """Desenha os cantos reforçados protegendo os limites da caixa."""
        largura = max(0, x2 - x1)
        altura = max(0, y2 - y1)
        
        comp_x = min(comprimento, largura // 2)
        comp_y = min(comprimento, altura // 2)

        if comp_x <= 0 or comp_y <= 0:
            return

        # Top-Left
        cv2.line(frame, (x1, y1), (x1 + comp_x, y1), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x1, y1), (x1, y1 + comp_y), cor, espessura, cv2.LINE_AA)
        # Top-Right
        cv2.line(frame, (x2, y1), (x2 - comp_x, y1), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x2, y1), (x2, y1 + comp_y), cor, espessura, cv2.LINE_AA)
        # Bottom-Left
        cv2.line(frame, (x1, y2), (x1 + comp_x, y2), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x1, y2), (x1, y2 - comp_y), cor, espessura, cv2.LINE_AA)
        # Bottom-Right
        cv2.line(frame, (x2, y2), (x2 - comp_x, y2), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x2, y2), (x2, y2 - comp_y), cor, espessura, cv2.LINE_AA)


    def _desenhar_caixa_delimitadora(self, frame, box, label, color=(0, 210, 255)):
        """
        Desenha caixa delimitadora moderna protegida contra overflow de coordenadas.
        """
        h_img, w_img = frame.shape[:2]

        # Garante que as coordenadas da caixa fiquem dentro do frame
        x1 = int(np.clip(box[0], 0, w_img - 1))
        y1 = int(np.clip(box[1], 0, h_img - 1))
        x2 = int(np.clip(box[2], 0, w_img - 1))
        y2 = int(np.clip(box[3], 0, h_img - 1))

        # Se a caixa for inválida ou colapsada, ignora o desenho
        if x2 <= x1 or y2 <= y1:
            return

        # Borda sutil de 1px
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)
        
        # Cantos estilizados
        self._desenhar_cantos(frame, x1, y1, x2, y2, color, espessura=2, comprimento=14)
        self._desenhar_cantos(frame, x1, y1, x2, y2, color, espessura=2, comprimento=14)

        # Configuração da tipografia
        fonte = cv2.FONT_HERSHEY_DUPLEX
        escala = 0.45
        espessura_txt = 1
        (largura_txt, altura_txt), baseline = cv2.getTextSize(label, fonte, escala, espessura_txt)

        # Determina a posição vertical do badge evitando sair da imagem
        padding = 4
        badge_h = altura_txt + (padding * 2)
        badge_w = largura_txt + (padding * 2)

        if y1 - badge_h >= 0:
            # Fica acima da caixa
            b_y1 = y1 - badge_h
            b_y2 = y1
            txt_y = y1 - padding - 1
        else:
            # Fica dentro do topo da caixa se não houver espaço em cima
            b_y1 = y1
            b_y2 = min(h_img, y1 + badge_h)
            txt_y = y1 + altura_txt + padding

        b_x1 = x1
        b_x2 = min(w_img, x1 + badge_w)
        txt_x = x1 + padding

        # Desenha o fundo da tag e o texto com coordenadas seguras
        cv2.rectangle(frame, (b_x1, b_y1), (b_x2, b_y2), color, -1)
        cv2.putText(frame, label, (txt_x, txt_y), fonte, escala, (15, 15, 15), espessura_txt, cv2.LINE_AA)


    def _desenhar_hud_topo(self, frame, class_count: dict, fps: float = None):
        largura = frame.shape[1]
        
        # Barra superior semitransparente
        sobreposicao = frame.copy()
        cv2.rectangle(sobreposicao, (0, 0), (largura, 42), (20, 20, 20), -1)
        cv2.addWeighted(sobreposicao, 0.65, frame, 0.35, 0, frame)
        cv2.line(frame, (0, 42), (largura, 42), (55, 55, 55), 1, cv2.LINE_AA)

        # Itens do HUD
        offset_x = 20
        fonte = cv2.FONT_HERSHEY_DUPLEX
        
        # Indicador de atividade
        cv2.circle(frame, (offset_x, 21), 5, (0, 230, 100), -1, cv2.LINE_AA)
        offset_x += 18
        cv2.putText(frame, "ONLINE", (offset_x, 26), fonte, 0.45, (230, 230, 230), 1, cv2.LINE_AA)
        offset_x += 80

        # Contadores
        for cls_name, count in class_count.items():
            texto = f"{cls_name.upper()}: {count}"
            (w, _), _ = cv2.getTextSize(texto, fonte, 0.45, 1)
            
            cv2.rectangle(frame, (offset_x - 6, 8), (offset_x + w + 6, 34), (45, 45, 45), -1)
            cv2.putText(frame, texto, (offset_x, 26), fonte, 0.45, (0, 215, 255), 1, cv2.LINE_AA)
            offset_x += w + 20
