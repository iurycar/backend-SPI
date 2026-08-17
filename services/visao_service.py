from collections import defaultdict
from ultralytics import YOLO
import numpy as np
import unicodedata
import platform
import cv2
import os

from repository.monitoramento_repository import MonitoramentoRepository
from repository.zonas_repository import ZonasRepository
from repository.epi_repository import EpiRepository

from models.alertas import Alerta
from models.cameras import Camera

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'assets', 'modelo', 'treinamento', 'weights', 'best.pt')

model = YOLO(MODEL_PATH)

# Verifica quais câmeras estão disponíveis no sistema (0, 1, 2, ...)
def get_plataform_camera():
    system_name = platform.system()

    if system_name == "Windows":
        print("Sistema operacional: Windows")
        return cv2.CAP_DSHOW
    elif system_name == "Linux":
        print("Sistema operacional: Linux")
        return cv2.CAP_V4L2
    else:
        print(f"Sistema operacional: {system_name} (usando configuração padrão)")
        return cv2.CAP_ANY

def find_camera():
    backend = get_plataform_camera()

    for index in range(5):  # Tenta abrir as câmeras de índice 0 a 4
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()

            if ret:
                print(f"Câmera encontrada no índice {index}")
                return index, backend

    return None, backend

cam_idx, backend = find_camera()

if cam_idx is None:
    raise RuntimeError("❌ Nenhuma câmera disponível foi encontrada.")

cap = cv2.VideoCapture(cam_idx, backend)

last_results = []

def get_last_results():
    return last_results

def generate_frames(connection, camera: Camera = None):
    global last_results

    # 1. Busca as zonas configuradas para essa câmera antes de iniciar o loop de frames
    id_camera_atual = camera.id if camera else 1 # Ajuste caso a câmera venha nula
    zonas_configuradas = zonas_de_monitoramento(connection, id_camera_atual)

    while True:
        ret, frame = cap.read()

        if not ret:
            print("⚠ Falha ao capturar frame.")
            break

        # 2. Desenha as zonas na tela com cv2.rectangle e sem acentos
        for class_name, poligonos in zonas_configuradas.items():
            # Remove acentos do nome da zona
            nome_zona_limpo = remover_acentos(class_name)
            
            for poligono in poligonos:
                # O cv2.boundingRect acha a caixa delimitadora perfeita de forma automática
                # sem se importar se o array tem 2 ou 3 dimensões
                x, y, w, h = cv2.boundingRect(poligono)
                
                # Desenha o retângulo: (x, y) é o canto superior esquerdo, 
                # e (x+w, y+h) é o canto inferior direito
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                
                # Escreve o texto
                cv2.putText(frame, f"Zona: {nome_zona_limpo}", (x, max(y - 10, 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        results = model(frame, stream=True, conf=0.5, iou=0.4)
        class_counts = defaultdict(int)
        detections = []

        # Debug: Exibe

        for r in results:
            for box in r.boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = model.names[cls]

                if conf < 0.5:
                    continue

                # 3. Calcular o centro do objeto detectado
                cx = int((xyxy[0] + xyxy[2]) / 2)
                cy = int((xyxy[1] + xyxy[3]) / 2)

                # 4. Verifica se a classe está restrita a uma ou mais zonas
                if class_name in zonas_configuradas:
                    esta_dentro_de_uma_zona = False
                    
                    for poligono in zonas_configuradas[class_name]:
                        is_inside = cv2.pointPolygonTest(poligono, (cx, cy), measureDist=False)
                        if is_inside >= 0:
                            esta_dentro_de_uma_zona = True
                            break
                    
                    if not esta_dentro_de_uma_zona:
                        continue

                # Remove acentos da detecção individual
                nome_deteccao_limpo = remover_acentos(class_name)
                label = f"{nome_deteccao_limpo} ({conf:.2f})"
                
                detections.append({"label": class_name, "confidence": conf})

                color = (0, 255, 0)
                cv2.rectangle(frame, (xyxy[0], xyxy[1]), (xyxy[2], xyxy[3]), color, 2)
                
                cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

                text_y = max(xyxy[1] - 10, 10)
                cv2.putText(frame, label, (xyxy[0], text_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                class_counts[class_name] += 1

        start_y = 30
        for idx, (name, count) in enumerate(class_counts.items()):
            # Remove acentos também do contador global
            nome_contador_limpo = remover_acentos(name)
            cv2.putText(frame, f"{nome_contador_limpo}: {count}", (10, start_y + idx * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        last_results = detections
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
        )

def zonas_de_monitoramento(connection, id_camera: int) -> dict:
    """
    ZONAS_DE_DETECCAO = {
        # Exemplo: Zona exclusiva para detectar 'pessoa' (pessoas)
        "pessoa": np.array([[50, 50], [300, 50], [300, 400], [50, 400]], np.int32),
    
        # Exemplo: Zona exclusiva para detectar 'luva' (luvas)
        "luva": np.array([[350, 50], [600, 50], [600, 400], [350, 400]], np.int32)
    }
    """

    try:
        connection.rollback()
    except Exception:
        pass

    epis = EpiRepository(connection)
    zonas = ZonasRepository(connection)
    monitorar = MonitoramentoRepository(connection)

    zonas_de_deteccao: dict = {}
    epis_dict: dict = {}
    zonas_dict: dict = {}
    
    monitoramento_lista = monitorar.get_monitoramentos_por_id_camera(id_camera)
    zonas_lista = zonas.get_zonas_por_id_camera(id_camera)
    epis_lista = epis.get_epis()

    # Montar o dicionário com a área da zonas e epis que devem ser detectadas (caso null não deve ter pessoa na área)

    for epi in epis_lista:
        epis_dict[epi.id] = epi.nome

    for zona in zonas_lista:
        x1, y1 = int(zona.x1), int(zona.y1)
        x2, y2 = int(zona.x2), int(zona.y2)

        zonas_dict[zona.id] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    for monitoramento in monitoramento_lista:
        id_zona = monitoramento.id_zona
        id_epi = monitoramento.id_epi

        coordenadas_brutas = zonas_dict.get(id_zona)

        if not coordenadas_brutas:
            continue

        # O reshape((-1, 1, 2)) força a matriz a ficar no formato exato que o OpenCV exige
        poligono = np.array(coordenadas_brutas, dtype=np.int32).reshape((-1, 1, 2)) 

        if id_epi is None:
            nome_classe = 'pessoa'
        else:
            nome_classe = epis_dict.get(id_epi)

            if not nome_classe:
                continue

        zonas_de_deteccao[nome_classe] = poligono

    return zonas_de_deteccao

def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    # Remove as marcas de acentuação para o OpenCV conseguir ler
    processo = unicodedata.normalize("NFD", texto)
    return "".join(c for c in processo if unicodedata.category(c) != "Mn")