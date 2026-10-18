from pathlib import Path
import cv2
from ultralytics import YOLO
import os

"""
    Script para processar vídeos e imagens usando o modelo YOLOv8 treinado.
    Ele salva os frames processados e as labels correspondentes em diretórios específicos.
    - Para vídeos, ele salva 1 frame a cada FRAME_STRIDE frames.
    - Para imagens, ele processa todas as imagens na pasta especificada.

    Configurações:
    - FRAME_STRIDE: Define a frequência de frames a serem salvos do vídeo.
    - CONF_THRESHOLD: Define o limiar de confiança para as detecções.
    - DEVICE: Define o dispositivo a ser usado para inferência (ex: "cuda" para GPU, "cpu" para CPU).
    - OUTPUT_DIR: Diretório onde os resultados serão salvos, incluindo subpastas para imagens e labels.
    - IMAGES_DIR: Subpasta para salvar os frames/imagens processadas.
    - LABELS_DIR: Subpasta para salvar os arquivos de label correspondentes.
"""

model = YOLO("assets/modelo/treinamento/best.pt")

# Diretórios de saída usando Pathlib
OUTPUT_DIR = Path("assets/modelo/active_learning/dataset_captura/videos/resultados")
IMAGES_DIR = OUTPUT_DIR / "images"
LABELS_DIR = OUTPUT_DIR / "labels"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

if not os.path.exists(LABELS_DIR):
    os.makedirs(LABELS_DIR)

IMAGES_DIR.mkdir(parents=True, exist_ok=True)
LABELS_DIR.mkdir(parents=True, exist_ok=True)

FRAME_STRIDE = 30     # Pular frames: 1 = salva todos; 15 = salva 1 a cada 15 frames
CONF_THRESHOLD = 0.5  # Limiar de confiança mínimo
DEVICE = "cuda"


def aplicar_rotacao(frame, rotacao: int):
    """Aplica a rotação necessária no frame antes da inferência."""
    if rotacao == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif rotacao == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    elif rotacao == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def processar_video(
    filename: str,
    path: str = "assets/modelo/active_learning/dataset_captura/videos",
    rotacao: int = 0
):
    video_path = Path(path) / filename

    if not video_path.exists():
        print(f"\n[ERRO] Arquivo não encontrado: {video_path}")
        return

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Não foi possível abrir o vídeo: {video_path}")

    frame_idx = 0
    saved_count = 0
    video_stem = video_path.stem  # Nome do vídeo sem extensão para prefixar arquivos

    print(f"\nProcessando vídeo: {video_path} ...\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Processa apenas nos passos definidos pelo stride
        if frame_idx % FRAME_STRIDE == 0:
            if rotacao in (90, 180, 270):
                frame = aplicar_rotacao(frame, rotacao)

            # Prefixo com nome do vídeo evita sobrescrita de múltiplos arquivos
            file_base = f"{video_stem}_frame_{frame_idx:06d}"
            img_filename = IMAGES_DIR / f"{file_base.strip()}.jpg"
            txt_filename = LABELS_DIR / f"{file_base.strip()}.txt"

            # Salva a imagem do frame
            cv2.imwrite(str(img_filename), frame)

            # Executa a inferência no frame já rotacionado
            results = model.predict(
                source=frame,
                conf=CONF_THRESHOLD,
                device=DEVICE,
                verbose=False
            )
            result = results[0]

            # Extrai caixas normalizadas e a confiança: <class_id> <x> <y> <w> <h> : <conf>
            linhas_txt = []
            if result.boxes is not None and len(result.boxes) > 0:
                classes = result.boxes.cls.int().tolist()
                coords = result.boxes.xywhn.tolist()
                conf = result.boxes.conf.tolist()

                for cls_id, (x, y, w, h), c in zip(classes, coords, conf):
                    linhas_txt.append(f"{cls_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f} : {c:.6f}")

            # Salva a label (.txt vazio se não houver detecção)
            with open(txt_filename, "w", encoding="utf-8") as f:
                if linhas_txt:
                    f.write("\n".join(linhas_txt) + "\n")

            saved_count += 1

        frame_idx += 1

    cap.release()
    print(f"\nConcluído! Total de {saved_count} pares (imagem/label) gerados em '{OUTPUT_DIR}'.\n")



def process_images(images_path: str = "assets/modelo/active_learning/dataset", output_path: str = "assets/modelo/active_learning/dataset_captura"):
    print(f"\nProcessando imagens em: {images_path} ...\n")
    model.predict(
        source=images_path,
        conf=CONF_THRESHOLD,
        save_txt=True,
        save_conf=False,
        project=output_path,
        name="dataset",
        exist_ok=True,
        device=DEVICE
    )
    print("\nProcessamento de imagens concluído!\n")


def menu():
    while True:
        print("""
=============================================
   SELECIONE O TIPO DE DETECÇÃO DESEJADA:
   (1) VÍDEO
   (2) FOTOS
   (0) ENCERRAR
=============================================""")
        entrada = input("\nDigite a opção: ").strip()

        if entrada == "1":
            filename = input("\nDigite o nome do arquivo de vídeo (ex: teste.mp4): ").strip()
            rot_input = input("Digite a rotação (0, 90, 180, 270) [Padrão: 0]: ").strip()
            rotacao = int(rot_input) if rot_input in ("90", "180", "270") else 0
            
            processar_video(filename=filename, rotacao=rotacao)

        elif entrada == "2":
            folder_path = str(input("\nDigite o caminho da pasta de imagens (ex: assets/modelo/active_learning/dataset): ")).strip()
            output_folder = str(input("\nDigite o caminho da pasta de saída (padrão: assets/modelo/active_learning/dataset_captura): ")).strip()
            
            process_images(images_path=folder_path, output_path=output_folder)

        elif entrada == "0":
            print("\nEncerrando o programa.")
            break
        else:
            print("\n[AVISO] Opção inválida. Tente novamente.")


if __name__ == "__main__":
    menu()