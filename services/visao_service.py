from collections import defaultdict
from ultralytics import YOLO
import platform
import cv2
import os

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

"""if cam_idx is None:
    raise RuntimeError("❌ Nenhuma câmera disponível foi encontrada.")"""

cap = cv2.VideoCapture(cam_idx, backend)

last_results = []

def get_last_results():
    return last_results

def generate_frames():
    global last_results

    """while True:
        ret, frame = cap.read()

        if not ret:
            print("⚠ Falha ao capturar frame.")
            break

        results = model(frame, stream=True, conf=0.5, iou=0.4)
        class_counts = defaultdict(int)
        detections = []

        for r in results:
            for box in r.boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                cls = int(box.cls[0])
                conf = float(box.conf[0])

                if conf < 0.5:
                    continue

                label = f"{model.names[cls]} ({conf:.2f})"
                detections.append({"label": model.names[cls], "confidence": conf})

                color = (0, 255, 0)
                cv2.rectangle(frame, (xyxy[0], xyxy[1]), (xyxy[2], xyxy[3]), color, 2)

                text_y = max(xyxy[1] - 10, 10)

                cv2.putText(frame, label, (xyxy[0], text_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                class_counts[model.names[cls]] += 1

        start_y = 30

        for idx, (name, count) in enumerate(class_counts.items()):
            cv2.putText(frame, f"{name}: {count}", (10, start_y + idx * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        last_results = detections

        ret, buffer = cv2.imencode('.jpg', frame)

        frame = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
        )"""