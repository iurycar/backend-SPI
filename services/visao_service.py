from collections import defaultdict
from ultralytics import YOLO
import numpy as np
import unicodedata
import platform
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

modelo = YOLO(MODEL_PATH)
modelo_pose = YOLO(MODEL_PATH_POSE)

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
        self.last_results = []
        self.cap = None
        self._alert_cache = {}

        cam_idx, backend = self.find_camera()

        if cam_idx is None:
            print("❌ Nenhuma câmera disponível encontrada.")
            return
    
        self.cap = cv2.VideoCapture(cam_idx, backend)


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

        zonas_configuradas = self.zonas_de_monitoramento(camera_id)

        if not zonas_configuradas:
            print(f"❌ Nenhuma zona configurada para a câmera com ID {camera_id}.")
            return
        
        while self.cap.isOpened():
            # Lê o próximo frame da câmera
            sucesso, frame = self.cap.read()

            if not sucesso:
                break

            # Realiza a detecção de objetos no frame
            detections, class_count = self.object_detection(frame, zonas_configuradas)

            # Atualiza a lista de detecções e desenha as zonas no frame
            for monitoramento in zonas_configuradas:
                nome = self.remover_acentos(monitoramento.nome)
                self.desenhar_zona(frame, monitoramento.regiao, nome)

            # Exibe a contagem de cada classe detectada no canto superior esquerdo do frame
            start_y = 30
            for idx, (cls_name, count) in enumerate(class_count.items()):
                cv2.putText(frame, f"{cls_name}: {count}", (10, start_y + idx * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.CORES.get('branco', (255, 255, 255)), 2)

            self.last_results = detections

            # Realiza a estimativa de pose no frame
            self.pose_estimation(frame, camera_id)

            # Codifica o frame em JPEG e o envia como resposta para o cliente
            sucesso, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
            )


    def get_last_results(self):
        return self.last_results


    def object_detection(self, frame, zonas_configuradas):
        """
            Realiza a detecção de objetos no frame e verifica se eles estão dentro das zonas configuradas, além de verificar se possuem o EPI obrigatório.
        """

        # Realiza a detecção de objetos no frame mascarado usando o modelo YOLO
        results_object = modelo.track(frame, persist=True, conf=0.5, iou=0.4, verbose=False)

        detections = []
        class_count = defaultdict(int)

        # Itera sobre os resultados da detecção
        for r in results_object:
            if r.boxes is None:
                continue

            # Itera sobre cada caixa detectada
            for box in r.boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int) # Obtém as coordenadas da caixa delimitadora
                cls = int(box.cls[0]) # Obtém a classe do objeto detectado
                conf = float(box.conf[0]) # Obtém a confiança da detecção

                # Obtém o ID do objeto rastreado (track_id) e o nome da classe (label_name)
                track_id = int(box.id[0]) if box.id is not None else -1
                label_name = modelo.names[cls].lower()

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


    def registrar_alerta_epi_incorreto(self, monitoramento: Zona, evento: str, track_id: int, severidade: int = 1) -> None:
        """
        Registra um alerta, evitando duplicidade por um curto período.
        """
        if monitoramento.id_monitorar is None:
            return

        cache_chave = (monitoramento.id_monitorar, evento, track_id)
        agora = time.monotonic()
        ultimo_alerta = self._alert_cache.get(cache_chave, 0)

        if agora - ultimo_alerta < 10:
            return

        setor = self.setores_repository.get_setor_por_id_zona(monitoramento.id)

        if setor:
            responsaveis = self.setores_repository.get_responsaveis_por_setor(setor.id)

            if not responsaveis:
                return

            for responsavel in responsaveis:
                if self.alertas_service.criar_alerta(monitoramento.id_monitorar, responsavel, evento):
                    self._alert_cache[cache_chave] = agora


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

            # Verifica o ângulo de rotação entre os ombros e quadris, caso seja maior que 30 graus, considera má postura
            dx_ombros: float = ombro_dir[0] - ombro_esq[0]
            dy_ombros: float = ombro_dir[1] - ombro_esq[1]
            angulo_ombros: float = math.degrees(math.atan2(abs(dy_ombros), abs(dx_ombros)))

            if angulo_ombros > 30:
                is_ma_postura = True
                motivo =  f"Rotação Excessiva do Tronco ({int(angulo_ombros)} graus)"

            return is_ma_postura, motivo, (int(ombro_esq[0]), int(ombro_esq[1])), (int(ombro_dir[0]), int(ombro_dir[1]))

        # ==============
        # Método de cálculo para indivíduo caído no chão
        # ==============
        elif metodo == "queda":
            ombro_esq: tuple[float, float] = kargs.get('ombro_esq')
            ombro_dir: tuple[float, float] = kargs.get('ombro_dir')
            quadril_esq: tuple[float, float] = kargs.get('quadril_esq')
            quadril_dir: tuple[float, float] = kargs.get('quadril_dir')

            # Avalia se a pessoa está caída no chão, verificando a posição dos ombros e quadris em relação ao eixo vertical da imagem. Se a altura dos ombros e quadris estiver muito baixa (próxima do chão), considera-se que a pessoa está caída.
            altura = min(ombro_esq[1], ombro_dir[1], quadril_esq[1], quadril_dir[1])

            if altura > 400:  # Ajuste este valor de acordo com a altura da câmera e a posição do chão na imagem
                is_ma_postura = True
                motivo = "Pessoa caída no chão"

            return is_ma_postura, motivo, (int(ombro_esq[0]), int(ombro_esq[1])), (int(quadril_dir[0]), int(quadril_dir[1]))


    def pose_estimation(self, frame, camera_id):
        """
        Implementa a lógica de estimativa de pose, desenha o esqueleto e 
        calcula a inclinação do tronco para gerar alertas de má postura.
        """
        # Mudança: Usar track para obter o ID da pessoa (necessário para o sistema de alertas não fazer spam)
        results = modelo_pose.track(frame, persist=True, conf=0.5, verbose=False)

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

                    cor_coluna = self.CORES.get('ciano', (0, 255, 0))

                    for p in [ombro_esq, ombro_dir, quadril_esq, quadril_dir]:
                        if p[0] <= 0 or p[1] <= 0:
                            cor_coluna = self.CORES.get('cinza', (120, 120, 120))
                            break
                        else:
                            is_ma_postura, motivo, pt_ombro, pt_quadril = self.avaliar_postura("tronco", ombro_esq, ombro_dir, quadril_esq, quadril_dir)
                            
                            if is_ma_postura:
                                cor_coluna = self.CORES.get('vermelho', (0, 0, 255))
                                cv2.putText(frame, f"ALERTA: {motivo}", 
                                            (pt_ombro[0] - 60, pt_ombro[1] - 20),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_coluna, 2)
                                
                                if track_id != -1:
                                    self.registrar_alerta_postura(track_id, motivo)
    
                            cv2.line(frame, pt_ombro, pt_quadril, cor_coluna, 4)

                            is_ma_postura_rotacao, motivo_rotacao, _, _ = self.avaliar_postura("rotacao", ombro_esq, ombro_dir, quadril_esq, quadril_dir)
                            
                            if is_ma_postura_rotacao:
                                cv2.putText(frame, f"ALERTA: {motivo_rotacao}", 
                                            (pt_ombro[0] - 60, pt_ombro[1] - 40),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.CORES.get('vermelho', (0, 0, 255)), 2)
                                
                                if track_id != -1:
                                    self.registrar_alerta_postura(track_id, motivo_rotacao)

                            is_caido, motivo_queda, _, _ = self.avaliar_postura("queda", ombro_esq, ombro_dir, quadril_esq, quadril_dir)

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

        # A chave do cache usa 'postura' para não conflitar com EPIs do mesmo trabalhador
        cache_chave = ('postura_fabrica', 'inclinacao_excessiva', track_id)
        agora = time.monotonic()
        ultimo_alerta = self._alert_cache.get(cache_chave, 0)

        # Cooldown de 10 segundos antes de alertar de novo sobre a mesma pessoa
        if agora - ultimo_alerta < 10:
            return

        setor = self.setores_repository.get_setor_por_id_camera(camera_id)
        
        if setor:
            responsaveis = self.setores_repository.get_responsaveis_por_setor(setor.id)

            if not responsaveis:
                return

            for responsavel in responsaveis:
                sucesso = self.alertas_service.criar_alerta(camera_id, responsavel, evento = motivo, severidade=severidade)
                if sucesso:
                    self._alert_cache[cache_chave] = agora
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

