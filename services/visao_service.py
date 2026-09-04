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
from services.alertas_service import AlertasService
from models.alertas import Alerta
from models.zonas import Zona

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


    def __init__(self, connection):
        self.connection = connection
        self.monitoramento_repository = MonitoramentoRepository(connection)
        self.setores_repository = SetoresRepository(connection)
        self.alertas_service = AlertasService(connection)

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

    def open_camera(self):
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


    def dentro_da_zona(self, box: tuple, regiao: list[tuple[int, int]]) -> bool:
        """
        Verifica se o centro da caixa delimitadora (box) está dentro do polígono definido por 'regiao'.
        """
        x1, y1, x2, y2 = box
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)

        pts = np.array(regiao, np.int32)
        return cv2.pointPolygonTest(pts, (cx, cy), False) >= 0


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
        xs = [p[0] for p in regiao]
        ys = [p[1] for p in regiao]
        return min(xs), min(ys), max(xs), max(ys)


    def desenhar_zona(self, frame, regiao, nome):
        """
        Desenha a zona no frame com base na região fornecida.
        """
        color = self.CORES.get('azul', (255, 0, 0))
        pts = np.array(regiao, np.int32)
        cv2.polylines(frame, [pts], True, color, 2)
        cv2.putText(frame, f"Zona: {nome}", (regiao[0][0], regiao[0][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


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


    def generate_frames(self, camera_id: int = 1):
        """
        Gera frames da câmera especificada, aplicando detecção de objetos e verificando se eles estão dentro das zonas configuradas.
        """
        self.ensure_models_loaded()
        zonas_configuradas = self.zonas_de_monitoramento(camera_id)

        if not zonas_configuradas:
            print(f"❌ Nenhuma zona configurada para a câmera com ID {camera_id}.")
            return

        if self.cap is None:
            self.open_camera()

        if self.cap is None or not self.cap.isOpened():
            return

        while self.cap.isOpened():
            sucesso, frame = self.cap.read()

            if not sucesso:
                break

            detections, class_count = self.object_detection(frame, zonas_configuradas)

            for monitoramento in zonas_configuradas:
                nome = self.remover_acentos(monitoramento.nome)
                self.desenhar_zona(frame, monitoramento.regiao, nome)

            start_y = 30
            for idx, (cls_name, count) in enumerate(class_count.items()):
                cv2.putText(frame, f"{cls_name}: {count}", (10, start_y + idx * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.CORES.get('branco', (255, 255, 255)), 2)

            self.last_results = detections
            self.pose_estimation(frame, camera_id)

            sucesso, buffer = cv2.imencode('.jpg', frame)
            if not sucesso:
                continue

            frame_bytes = buffer.tobytes()

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
            )

    def run_video_loop(self, camera_id: int = 1, frame_queue=None, last_results=None, stop_event=None):
        """Executa o loop de processamento em um processo separado."""
        self.ensure_models_loaded()
        zonas_configuradas = self.zonas_de_monitoramento(camera_id)

        if not zonas_configuradas:
            if last_results is not None:
                last_results['detections'] = []
                last_results['class_count'] = {}
            return

        self.cap = self.open_camera()

        if self.cap is None or not self.cap.isOpened():
            if last_results is not None:
                last_results['detections'] = []
                last_results['class_count'] = {}
            return

        try:
            while not (stop_event is not None and stop_event.is_set()):
                sucesso, frame = self.cap.read()

                if not sucesso:
                    break

                detections, class_count = self.object_detection(frame, zonas_configuradas)

                for monitoramento in zonas_configuradas:
                    nome = self.remover_acentos(monitoramento.nome)
                    self.desenhar_zona(frame, monitoramento.regiao, nome)

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

        frame_limpo = frame.copy()

        # Itera sobre os resultados da detecção
        for r in results_object:
            if r.boxes is None:
                continue

            img_altura, img_largura = frame.shape[:2]

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

                # Itera sobre as zonas configuradas para verificar se o objeto está dentro de alguma delas
                for monitoramento in zonas_configuradas:

                    if self.caixas_intersectam(xyxy, self.regiao_para_caixa(monitoramento.regiao)):

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
                                    self.desenhar_caixa_delimitadora(frame, xyxy, f"{label_name.capitalize().replace('_', ' ')} (Requisitado)", self.CORES.get('verde', (0, 255, 0)))

                        # Verifica se o objeto é 'pessoa' e se está dentro da zona que não permite pessoas
                        if label_name == "pessoa" and not self.zona_requer_classe(monitoramento.epis_categoria, "pessoa", monitoramento.permitido):
                            self.desenhar_caixa_delimitadora(frame, xyxy, f"{label_name} ID:{track_id} (Zona Restrita)", self.CORES.get('vermelho', (0, 0, 255)))
                            self.registrar_alerta_epi_incorreto(monitoramento, "Pessoa em zona restrita", track_id, severidade=3)


                if label_name == "pessoa" and self.zona_requer_classe(monitoramento.epis_categoria, "pessoa"):
                    self.desenhar_caixa_delimitadora(frame, xyxy, f"{label_name} ID:{track_id}", self.CORES.get('magenta', (255, 0, 255)))
                
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

        # Chave única de lock (cadeado) de cooldown (tempo de recarga) de 10 segundos para evitar alertas duplicados
        cache_chave = f"lock:alerta:epi:{monitoramento.id_monitorar}:{evento}:{track_id}"

        # Se a chave já existir, significa que um alerta recente já foi registrado para este evento e track_id
        if not self.redis_client.set(cache_chave, "1", ex=10, nx=True):
            return # Já existe um alerta recente para este evento e track_id

        setor = self.setores_repository.get_setor_por_id_zona(monitoramento.id)

        if setor:
            responsaveis = self.setores_repository.get_responsaveis_por_setor(setor.id)

            if responsaveis:
                for responsavel in responsaveis:
                    self.alertas_service.criar_alerta(monitoramento, responsavel, evento, severidade=severidade)

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
                            cv2.circle(frame, (x, y), 4, self.CORES.get('verde', (0, 255, 0)), -1)

                    # Desenhar as conexões do esqueleto
                    for p1, p2 in esqueleto_conexoes:
                        x1, y1 = int(individual[p1][0]), int(individual[p1][1])
                        x2, y2 = int(individual[p2][0]), int(individual[p2][1])
                        if (x1 > 0 and y1 > 0) and (x2 > 0 and y2 > 0):
                            cv2.line(frame, (x1, y1), (x2, y2), self.CORES.get('magenta', (255, 0, 255)), 2)

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
                            cv2.putText(frame, f"ALERTA: {motivo}", 
                                        (pt_ombro[0] - 60, pt_ombro[1] - 20),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_coluna, 2)
                            
                            if track_id != -1:
                                self.registrar_alerta_postura(camera_id, track_id, motivo)
                                
                        cv2.line(frame, pt_ombro, pt_quadril, cor_coluna, 4)

                        # --- AVALIAÇÃO DA ROTAÇÃO ---
                        is_ma_postura_rotacao, motivo_rotacao, _, _ = self.avaliar_postura(
                            "rotacao", 
                            ombro_esq=ombro_esq, ombro_dir=ombro_dir, 
                            quadril_esq=quadril_esq, quadril_dir=quadril_dir
                        )
                        
                        if is_ma_postura_rotacao:
                            cv2.putText(frame, f"ALERTA: {motivo_rotacao}", 
                                        (pt_ombro[0] - 60, pt_ombro[1] - 40),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.CORES.get('vermelho', (0, 0, 255)), 2)
                            
                            if track_id != -1:
                                self.registrar_alerta_postura(camera_id, track_id, motivo_rotacao)

                        # --- AVALIAÇÃO DE QUEDA ---
                        is_caido, motivo_queda, _, _ = self.avaliar_postura(
                            "queda", 
                            ombro_esq=ombro_esq, ombro_dir=ombro_dir, 
                            quadril_esq=quadril_esq, quadril_dir=quadril_dir
                        )

                        if is_caido:
                            cv2.putText(frame, f"ALERTA: {motivo_queda}", 
                                        (pt_ombro[0] - 60, pt_ombro[1] - 60),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.CORES.get('vermelho', (0, 0, 255)), 2)
                            
                            if track_id != -1:
                                self.registrar_alerta_postura(camera_id, track_id, motivo_queda, severidade=3)

    def registrar_alerta_postura(self, camera_id: int, track_id: int, motivo: str, severidade: int = 1) -> None:
        """
        Registra um alerta de má postura no banco de dados, evitando duplicidade por ID.
        """

        cache_chave = f"lock:alerta:postura:{camera_id}:{track_id}:{motivo}"

        # Evita alertas duplicados para o mesmo track_id e motivo dentro de um período de 10 segundos
        if not self.redis_client.set(cache_chave, "1", ex=10, nx=True):
            return
        
        setor = self.setores_repository.get_setor_por_id_camera(camera_id)
        
        if setor:
            responsaveis = self.setores_repository.get_responsaveis_por_setor(setor.id)

            if responsaveis:  
                for responsavel in responsaveis:
                    sucesso = self.alertas_service.criar_alerta(camera_id, responsavel, evento = motivo, severidade=severidade)

                    if sucesso:
                        print(f"⚠️ Má postura detectada - ID: {track_id}")


    def desenhar_caixa_delimitadora(self, frame, box, label, color=(0, 255, 0)):
        """
        Desenha uma caixa delimitadora no frame com o rótulo fornecido.
        """
        x1, y1, x2, y2 = box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, max(y1 - 10, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    def remover_acentos(self, texto: str) -> str:
        if not texto:
            return ""
        processo = unicodedata.normalize("NFD", texto)
        return processo.encode("ascii", "ignore").decode("utf-8")

