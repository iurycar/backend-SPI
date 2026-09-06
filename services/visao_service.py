from collections import defaultdict
from extensions import REDIS_URL
from ultralytics import YOLO
import numpy as np
import unicodedata
import threading
import platform
import redis
import math
import time
import cv2
import os

from repository.monitoramento_repository import MonitoramentoRepository
from repository.setores_repository import SetoresRepository
from services.cameras_service import CamerasService
from services.alertas_service import AlertasService
from models.alertas import Alerta
from models.zonas import Zona

from tasks.alarme_task import enviar_comando

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'weights', 'best.pt')
MODEL_PATH_POSE = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'weights', 'yolov8s-pose.pt')

class VisaoService:
    EPI_CLASSE_POR_LABEL = {
        'com_capacete': 'capacete',
        'sem_capacete': 'capacete',
        'com_luva': 'luva',
        'sem_luva': 'luva',
        'com_oculos': 'oculos',
        'com_oculos_normal': 'oculos',
        'sem_oculos': 'oculos',
        'com_mascara': 'mascara',
        'sem_mascara': 'mascara',
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
        self.setores_repository = SetoresRepository(connection)
        self.alertas_service = AlertasService(connection)
        self.cameras_service = CamerasService(connection)

        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)

        self.last_results = []
        self.cap = None
        self.modelo = None
        self.modelo_pose = None

        self.active_learning_dir = os.path.join(BASE_DIR, 'assets', 'modelo', 'active_learning', 'dataset_captura')
        self.al_img_dir = os.path.join(self.active_learning_dir, 'images')
        self.al_lbl_dir = os.path.join(self.active_learning_dir, 'labels')
        self.flag_path = os.path.join(self.active_learning_dir, 'active_learning.flag')
        
        os.makedirs(self.al_img_dir, exist_ok=True)
        os.makedirs(self.al_lbl_dir, exist_ok=True)
        self._al_cooldown = {}

    def ensure_models_loaded(self):
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

        rtsp_url = None

        try:
            # Busca os dados da câmera por ID
            camera = self.cameras_service.obter_camera_por_id(camera_id)

            if camera:
                # Pega o RTSP da câmera
                rtsp_url = camera.get('ip') if isinstance(camera, dict) else getattr(camera, 'ip', None)

        except Exception as e:
            print(f"❌ Erro ao obter RTSP da câmera {camera_id}: {e}")


        # Se tiver URL RTSP, abre via FFMPEG forçando TCP
        if rtsp_url:
            print(f"🔗 Conectando ao RTSP da câmera {camera_id}: {rtsp_url}")

            # Define flags do FFmpeg via variáveis de ambiente para reduzir latência
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = "rtsp_transport;tcp|buffer_size;1024000|max_delay;500000"

            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

            # Limita buffer interno do OpenCV para evitar delay acumulado
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if cap.isOpened():
                self.cap = cap
                return self.cap
            else:
                print(f"❌ Falha ao abrir RTSP da câmera {camera_id}. Tentando fallback para webcam local.")

        # Fallback para webcam local
        cam_idx, backend = self.find_camera()

        if cam_idx is None:
            print("❌ Nenhuma câmera disponível encontrada.")
            return None

        self.cap = cv2.VideoCapture(cam_idx, backend)
        return self.cap


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


    def find_camera(self):
        """
        Encontra uma câmera disponível no sistema.
        """
        
        cameras = self.cameras_service.listar_cameras()
        backend = self.get_plataform_camera()

        for index in range(5):
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                sucesso, _ = cap.read()
                cap.release()

                if sucesso:
                    print(f"Câmera encontrada no índice {index}")
                    return index, backend

        return None, backend


    def zonas_de_monitoramento(self, id_camera: int) -> list[Zona]:
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


    def caixas_intersectam(self, caixa1: tuple, caixa2: tuple) -> bool:
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


    def classe_epi_por_label(self, label: str) -> str | None:
        if not label:
            return None
        return self.EPI_CLASSE_POR_LABEL.get(str(label).strip().lower())


    def zona_requer_classe(self, categorias_permitidas: list[str] | None, classe: str, permitido: bool = False) -> bool:
        if classe == "pessoa" and permitido:
            return True

        if not categorias_permitidas:
            return False

        for categoria in categorias_permitidas:
            categoria_normalizada = self.classe_epi_por_label(categoria) or str(categoria).strip().lower()

            if categoria_normalizada == classe:
                return True

        return False


    def run_video_loop(self, 
                       camera_id: int = 1, 
                       frame_queue=None, 
                       last_results=None, 
                       stop_event=None, 
                       reload_zones_event=None
        ):

        """Executa o loop de processamento em um processo separado com reconexão automática."""
        self.ensure_models_loaded()
        zonas_configuradas = self.zonas_de_monitoramento(camera_id)

        self.cap = self.open_camera(camera_id)

        try:
            while not (stop_event is not None and stop_event.is_set()):
                if reload_zones_event is not None and reload_zones_event.is_set():
                    print(f"🔄 Recarregando zonas da câmera {camera_id} no processo de visão...")
                    zonas_configuradas = self.zonas_de_monitoramento(camera_id)
                    reload_zones_event.clear()

                if self.cap is None or not self.cap.isOpened():
                    print(f"🔄 Tentando reconectar à câmera {camera_id} em 5s...")
                    time.sleep(5)
                    self.cap = self.open_camera(camera_id)
                    continue

                sucesso, frame = self.cap.read()

                if not sucesso:
                    print(f"⚠️ Perda de sinal no stream da câmera {camera_id}. Reiniciando captura...")
                    if last_results is not None:
                        last_results['connected'] = False # Marca que o RTSP caiu
                    self.cap.release()
                    self.cap = None
                    time.sleep(2)
                    continue

                if last_results is not None:
                    last_results['connected'] = True # Marca que o RTSP está ativo
                    last_results['last_frame_time'] = time.time()

                detections, class_count = self.object_detection(frame, zonas_configuradas)

                start_y = 30
                for idx, (cls_name, count) in enumerate(class_count.items()):
                    cv2.putText(frame, f"{cls_name}: {count}", (10, start_y + idx * 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.CORES.get('branco', (255, 255, 255)), 2)

                self.last_results = detections
                if last_results is not None:
                    last_results['detections'] = detections
                    last_results['class_count'] = dict(class_count)

                self.pose_estimation(frame, camera_id)

                sucesso, buffer = cv2.imencode('.jpg', frame)
                if sucesso and frame_queue is not None:
                    try:
                        if frame_queue.full():
                            try:
                                frame_queue.get_nowait()  # Remove o frame antigo se a fila estiver cheia
                            except Exception:
                                pass
                        frame_queue.put(buffer.tobytes(), block=False)

                    except Exception:
                        pass
        
        finally:
            if self.cap is not None:
                self.cap.release()
            self.cap = None


    def get_last_results(self):
        return self.last_results


    def processar_active_learning(self, frame_limpo, boxes, img_shape):
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
        

    def object_detection(self, frame, zonas_configuradas):
        """
            Realiza a detecção de objetos no frame e verifica se eles estão dentro das zonas configuradas, além de verificar se possuem o EPI obrigatório.
        """
        self.ensure_models_loaded()

        results_object = self.modelo.track(frame, persist=True, conf=0.5, iou=0.4, verbose=False)

        detections = []
        class_count = defaultdict(int)
        img_altura, img_largura = frame.shape[:2]

        frame_limpo = frame.copy()

        # Itera sobre os resultados da detecção
        for r in results_object:
            if r.boxes is None:
                continue

            self.processar_active_learning(frame_limpo, r.boxes, (img_altura, img_largura))

            # Itera sobre cada caixa detectada
            for box in r.boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int) # Obtém as coordenadas da caixa delimitadora
                cls = int(box.cls[0]) # Obtém a classe do objeto detectado
                conf = float(box.conf[0]) # Obtém a confiança da detecção

                # Obtém o ID do objeto rastreado (track_id) e o nome da classe (label_name)
                track_id = int(box.id[0]) if box.id is not None else -1
                label_name = self.modelo.names[cls].lower()

                zonas_do_objeto = [] # Lista para armazenar os IDs das zonas em que o objeto foi detectado
                cor_status = 'verde'

                # Itera sobre as zonas configuradas para verificar se o objeto está dentro de alguma delas
                for monitoramento in zonas_configuradas:
                    regiao_px = self.regiao_para_pixels(monitoramento.regiao, img_largura, img_altura)
                    if self.caixas_intersectam(xyxy, self.regiao_para_caixa(regiao_px)):

                        # Verifica se o objeto é requisitado na zona
                        if self.zona_requer_classe(monitoramento.epis_categoria, self.classe_epi_por_label(label_name), monitoramento.permitido):
                            zonas_do_objeto.append(monitoramento.id)

                            # Verifica se o objeto é 'com_...' ou 'sem_...' e se está dentro da zona que requer o EPI correspondente
                            if label_name.startswith("sem_"):
                                self.desenhar_caixa_delimitadora(frame, xyxy, f"{label_name}", self.CORES.get('vermelho', (0, 0, 255)))
                                self.registrar_alerta_epi_incorreto(monitoramento, f"Sem EPI necessário: {self.classe_epi_por_label(label_name)}", track_id, severidade=2)
                            else:
                                # Verifica se o objeto é normal, caso seja desenha a caixa delimitadora em amarelo e registra o alerta de EPI incorreto
                                if label_name.endswith("_normal"):
                                    self.desenhar_caixa_delimitadora(frame, xyxy, f"{label_name.capitalize().replace('_', ' ')}", self.CORES.get('amarelo', (0, 255, 255)))
                                    self.registrar_alerta_epi_incorreto(monitoramento, f"Equipamento inadequado: {self.classe_epi_por_label(label_name)}", track_id, severidade=1)
                                else:
                                    self.desenhar_caixa_delimitadora(frame, xyxy, f"{label_name.capitalize().replace('_', ' ')}", self.CORES.get('verde', (0, 255, 255)))
                                            
                        # Verifica se o objeto é 'pessoa' e se está dentro da zona que não permite pessoas
                        if label_name == "pessoa" and not self.zona_requer_classe(monitoramento.epis_categoria, "pessoa", monitoramento.permitido):
                            self.desenhar_caixa_delimitadora(frame, xyxy, f"{label_name} ID:{track_id} (Zona Restrita)", self.CORES.get('vermelho', (0, 0, 255)))
                            self.registrar_alerta_epi_incorreto(monitoramento, "Pessoa em zona restrita", track_id, severidade=3)
                
                class_count[label_name] += 1

                # Adiciona a detecção à lista de detecções, associando-a às zonas em que o objeto foi detectado
                for z_id in zonas_do_objeto:
                    detections.append({
                        "id": track_id,
                        "label": label_name,
                        "confidence": conf,
                        "zona": z_id
                    })

        return detections, class_count

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

    def registrar_alerta_epi_incorreto(self, monitoramento: Zona, evento: str, track_id: int, severidade: int = 1) -> None:
        """
        Registra um alerta, evitando duplicidade por um curto período.
        """

        if monitoramento.id_monitorar is None:
            return

        # Chave única de lock (cadeado) de cooldown (tempo de recarga) de 30 segundos para evitar alertas duplicados
        cache_chave = f"lock:alerta:epi:{monitoramento.id_monitorar}:{evento}:{track_id}"

        # Se a chave já existir, significa que um alerta recente já foi registrado para este evento e track_id
        if not self.redis_client.set(cache_chave, "1", ex=30, nx=True):
            return # Já existe um alerta recente para este evento e track_id

        setor = self.setores_repository.get_setor_por_id_zona(monitoramento.id)
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

    def avaliar_postura(self, metodo, **kargs):
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
                motivo = f"Inclinacao Lateral ({int(angulo)} graus)"
            elif razao_tronco < LIMITE_RAZAO_FRONTAL:
                is_ma_postura = True
                motivo = f"Curvado de Frente (Razao: {razao_tronco:.2f})"

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
                motivo = f"Rotação/Torção Excessiva ({int(diferenca_rotacao)} graus)"

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
                motivo = f"Pessoa caída no chão (Prop: {proporcao:.2f})"

            # Calcula o ponto central do corpo para exibir a mensagem corretamente
            centro_x = int((min_x + max_x) / 2)
            centro_y = int((min_y + max_y) / 2)

            return is_ma_postura, motivo, (centro_x, centro_y), (centro_x, centro_y)


    def pose_estimation(self, frame, camera_id):
        """
        Implementa a lógica de estimativa de pose, desenha o esqueleto e 
        calcula a inclinação do tronco para gerar alertas de má postura.
        """
        self.ensure_models_loaded()
        results = self.modelo_pose.track(frame, persist=True, conf=0.5, verbose=False)

        esqueleto_conexoes = [
            (0, 1), (0, 2), (1, 3), (2, 4),            
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),   
            (5, 11), (6, 12), (11, 12),                
            (11, 13), (13, 15), (12, 14), (14, 16)     
        ]

        for result in results:
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
                        is_ma_postura, motivo, pt_ombro, pt_quadril = self.avaliar_postura(
                            "tronco", 
                            ombro_esq=ombro_esq, ombro_dir=ombro_dir, 
                            quadril_esq=quadril_esq, quadril_dir=quadril_dir
                        )
                        
                        if is_ma_postura:
                            cor_coluna = self.CORES.get('vermelho', (0, 0, 255))
                            """cv2.putText(frame, f"ALERTA: {motivo}", 
                                        (pt_ombro[0] - 60, pt_ombro[1] - 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_coluna, 2)"""
                            
                            if track_id != -1:
                                self.registrar_alerta_postura(camera_id, track_id, motivo)
                                
                        cv2.line(frame, pt_ombro, pt_quadril, cor_coluna, 4, cv2.LINE_AA)

                        # --- AVALIAÇÃO DA ROTAÇÃO ---
                        is_ma_postura_rotacao, motivo_rotacao, _, _ = self.avaliar_postura(
                            "rotacao", 
                            ombro_esq=ombro_esq, ombro_dir=ombro_dir, 
                            quadril_esq=quadril_esq, quadril_dir=quadril_dir
                        )
                        
                        if is_ma_postura_rotacao:
                            """cv2.putText(frame, f"ALERTA: {motivo_rotacao}", 
                                        (pt_ombro[0] - 60, pt_ombro[1] - 40),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.CORES.get('vermelho', (0, 0, 255)), 2)"""

                            if track_id != -1:
                                self.registrar_alerta_postura(camera_id, track_id, motivo_rotacao)

                        # --- AVALIAÇÃO DE QUEDA ---
                        is_caido, motivo_queda, _, _ = self.avaliar_postura(
                            "queda", 
                            ombro_esq=ombro_esq, ombro_dir=ombro_dir, 
                            quadril_esq=quadril_esq, quadril_dir=quadril_dir
                        )

                        if is_caido:
                            """cv2.putText(frame, f"ALERTA: {motivo_queda}", 
                                        (pt_ombro[0] - 60, pt_ombro[1] - 60),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.CORES.get('vermelho', (0, 0, 255)), 2)"""
                            
                            if track_id != -1:
                                self.registrar_alerta_postura(camera_id, track_id, motivo_queda, severidade=3)


    def registrar_alerta_postura(self, camera_id: int, track_id: int, motivo: str, severidade: int = 1) -> None:
        """
        Registra um alerta de má postura no banco de dados, evitando duplicidade por ID.
        """

        cache_chave = f"lock:alerta:postura:{camera_id}:{track_id}:{motivo}"

        # Evita alertas duplicados para o mesmo track_id e motivo dentro de um período de 30 segundos
        if not self.redis_client.set(cache_chave, "1", ex=30, nx=True):
            return

        zonas = self.zonas_de_monitoramento(camera_id)

        if not zonas:
            return

        zona_alvo = zonas[0]    
        
        setor = self.setores_repository.get_setor_por_id_camera(camera_id)
        
        if setor:
            responsaveis = self.setores_repository.get_responsaveis_por_setor(setor.id)
            sucesso = self.alertas_service.criar_alerta(
                monitoramento=zona_alvo,
                id_usuario=responsaveis[0] if responsaveis else None,
                evento = motivo, 
                severidade=severidade,
                destinatarios=responsaveis
            )

            if sucesso:
                print(f"⚠️ Má postura detectada - ID: {track_id}")


    # ==================================================
    # Funções para embelezar o UI do vídeo, desenhando zonas, caixas e cantos estilizados
    # ==================================================
    def desenhar_cantos(self, frame, x1, y1, x2, y2, cor, espessura=2, comprimento=12):
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


    def desenhar_caixa_delimitadora(self, frame, box, label, color=(0, 210, 255)):
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
        self.desenhar_cantos(frame, x1, y1, x2, y2, color, espessura=2, comprimento=14)

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


    def desenhar_hud_topo(frame, class_count: dict, fps: float = None):
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
            
    
    def remover_acentos(self, texto: str) -> str:
        if not texto:
            return ""
        processo = unicodedata.normalize("NFD", texto)
        return processo.encode("ascii", "ignore").decode("utf-8")

