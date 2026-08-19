from collections import defaultdict
from ultralytics import YOLO
import numpy as np
import unicodedata
import platform
import cv2
import os

from repository.monitoramento_repository import MonitoramentoRepository
from services.alertas_service import AlertasService
from models.alertas import Alerta
from models.zonas import Zona

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'weights', 'best.pt')
MODEL_PATH_POSE = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'weights', 'yolov8n-pose.pt')

modelo = YOLO(MODEL_PATH)
modelo_pose = YOLO(MODEL_PATH_POSE)

class VisaoService:
    def __init__(self, connection):
        self.connection = connection
        self.monitoramento_repository = MonitoramentoRepository(connection)
        self.alertas_service = AlertasService(connection)
        self.last_results = []
        self.cap = None

        cam_idx, backend = self.find_camera()
        
        if cam_idx is None:
            raise RuntimeError("❌ Nenhuma câmera disponível foi encontrada.")
    
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

    def desenhar_zona(self, frame, regiao, nome):
        """
        Desenha a zona no frame com base na região fornecida.
        """
        color = (255, 0, 0)
        pts = np.array(regiao, np.int32)
        cv2.polylines(frame, [pts], True, color, 2)
        cv2.putText(frame, f"Zona: {nome}", (regiao[0][0], regiao[0][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def generate_frames(self, camera_id: int = 1):
        """
        Gera frames da câmera especificada, aplicando detecção de objetos e verificando se eles estão dentro das zonas configuradas.
        """

        # ==========================
        # TODO: Depois precisamos quebrar a função em funções menores para ficar mais legível
        # ==========================

        zonas_configuradas = self.zonas_de_monitoramento(camera_id)

        if not zonas_configuradas:
            print(f"❌ Nenhuma zona configurada para a câmera com ID {camera_id}.")
            return
        
        while self.cap.isOpened():
            # Lê o próximo frame da câmera
            sucesso, frame = self.cap.read()

            if not sucesso:
                break

            # Cria uma máscara para as zonas configuradas
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)

            # Preenche a máscara com as regiões das zonas configuradas
            for monitoramento in zonas_configuradas:
                pts = np.array(monitoramento.regiao, np.int32)
                cv2.fillPoly(mask, [pts], 255)

            # Aplica a máscara ao frame original para manter apenas as regiões das zonas configuradas
            masked_frame = cv2.bitwise_and(frame, frame, mask=mask)

            # Realiza a detecção de objetos no frame mascarado usando o modelo YOLO
            results_object = modelo.track(masked_frame, persist=True, conf=0.5, iou=0.4, verbose=False)

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

                    # Verifica se o objeto detectado está dentro de alguma zona configurada e se possui o EPI obrigatório
                    objeto_valido_na_zona = False
                    zonas_do_objeto = []

                    # Itera sobre as zonas configuradas para verificar se o objeto está dentro de alguma delas
                    for monitoramento in zonas_configuradas:
                        if self.dentro_da_zona(xyxy, monitoramento.regiao):    
                            if label_name in monitoramento.epis_categoria:
                                objeto_valido_na_zona = True
                                zonas_do_objeto.append(monitoramento.id)

                    # Se o objeto não estiver dentro de nenhuma zona válida ou não tiver 
                    # o EPI obrigatório, ele será ignorado POR ENQUANTO
                    # TODO: Implementar lógica de alertas para pessoas sem EPI obrigatório
                    # Se a pessoa estiver dentro da zona, mas não tiver o EPI obrigatório, isso deve gerar um alerta
                    if not objeto_valido_na_zona:
                        print(f"Objeto '{label_name}' com ID {track_id} detectado fora da zona ou sem EPI obrigatório.")
                        continue

                    if label_name != "pessoa":
                        color = (0, 255, 0)
                    else: 
                        color = (0, 0, 255)

                    # Desenha a caixa delimitadora e o rótulo no frame
                    cv2.rectangle(frame, (xyxy[0], xyxy[1]), (xyxy[2], xyxy[3]), color, 2)
                    cv2.putText(frame, f"{label_name} ID:{track_id}",
                                (xyxy[0], max(xyxy[1]-10, 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                    class_count[label_name] += 1

                    # Adiciona a detecção à lista de detecções, associando-a às zonas em que o objeto foi detectado
                    for z_id in zonas_do_objeto:
                        detections.append({
                            "id": track_id,
                            "label": label_name,
                            "confidence": conf,
                            "zona": z_id
                        })

            # Atualiza a lista de detecções e desenha as zonas no frame
            for monitoramento in zonas_configuradas:
                nome = self.remover_acentos(monitoramento.nome)
                self.desenhar_zona(frame, monitoramento.regiao, nome)

            # Exibe a contagem de cada classe detectada no canto superior esquerdo do frame
            start_y = 30
            for idx, (cls_name, count) in enumerate(class_count.items()):
                cv2.putText(frame, f"{cls_name}: {count}", (10, start_y + idx * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            self.last_results = detections

            # TODO: Implementar a lógica de estimativa de pose para detectar se a pessoa 
            # está com uma postura adequada.
            self.pose_estimation(frame)

            # Codifica o frame em JPEG e o envia como resposta para o cliente
            sucesso, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
            )

    def get_last_results(self):
        return self.last_results

    def pose_estimation(self, frame):
        """
        Implementa a lógica de estimativa de pose para detectar os pontos 
        e desenhar os eixos (esqueleto) da pessoa.
        """
        results = modelo_pose.predict(frame, conf=0.5, verbose=False)

        esqueleto_conexoes = [
            (0, 1), (0, 2), (1, 3), (2, 4),            # Rosto (Olhos, Nariz e Orelhas)
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),   # Braços e Ombros
            (5, 11), (6, 12), (11, 12),                # Tronco
            (11, 13), (13, 15), (12, 14), (14, 16)     # Pernas
        ]

        for result in results:
            # Verifica se keypoints não é nulo E se contém alguma detecção
            if result.keypoints is not None and len(result.keypoints) > 0:
                keypoints_list = result.keypoints.xy.cpu().numpy()

                for individual in keypoints_list:
                    # PREVENÇÃO DO ERRO: Garante que o array tem os 17 pontos esperados
                    if len(individual) < 17:
                        continue

                    # 1. Desenhar os pontos (Articulações)
                    for ponto in individual:
                        x, y = int(ponto[0]), int(ponto[1])
                        
                        if x > 0 and y > 0:
                            cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)

                    # 2. Desenhar os eixos (Esqueleto)
                    for p1, p2 in esqueleto_conexoes:
                        x1, y1 = int(individual[p1][0]), int(individual[p1][1])
                        x2, y2 = int(individual[p2][0]), int(individual[p2][1])

                        if (x1 > 0 and y1 > 0) and (x2 > 0 and y2 > 0):
                            cv2.line(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)

    def gerar_alertas(self) -> list[Alerta]:
        """
        TODO: Implementar a lógica para gerar alertas com base nas detecções atuais.
        """
        pass
    
    def remover_acentos(self, texto: str) -> str:
        if not texto:
            return ""
        processo = unicodedata.normalize("NFD", texto)
        return processo.encode("ascii", "ignore").decode("utf-8")