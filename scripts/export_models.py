"""
Exporta os modelos .pt para um runtime mais rápido em CPU. Rode 1x (e de novo a cada novo treino).

    pip install openvino            # backend openvino   (nncf também, se for usar --int8)
    pip install onnx onnxruntime    # backend onnx
    pip install ncnn                # backend ncnn

    python scripts/export_models.py --backend openvino --det-imgsz 384,640 --pose-imgsz 384,480
    python scripts/export_models.py --backend openvino --int8 --data assets/modelo/dataset.yaml   # opcional

Dica: exporte com a MESMA proporção da câmera. Para 16:9 use altura/largura múltiplas de 32
(ex.: 384x640). Um export quadrado 640x640 gasta ~40% de cálculo em padding preto.
Os valores têm que ser os mesmos de DET_IMGSZ / POSE_IMGSZ usados em produção.
"""
import argparse
import os

from ultralytics import YOLO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DET_PT = os.path.join(ROOT, "assets", "modelo", "treinamento", "best.pt")
POSE_PT = os.path.join(ROOT, "assets", "modelo", "treinamento", "yolov8m-pose.pt")


def parse_imgsz(txt: str):
    p = [int(x) for x in txt.replace("x", ",").split(",") if x.strip()]
    return p[0] if len(p) == 1 else p


def export(pt_path, task, imgsz, backend, int8, data):
    if not os.path.exists(pt_path):
        print(f"⚠️  {pt_path} não encontrado — pulando.")
        return
    kw = dict(format=backend, imgsz=imgsz, half=False, dynamic=False, batch=1)
    if backend == "onnx":
        kw["simplify"] = True
    if backend == "openvino" and int8:
        kw.update(int8=True, data=data)
    print(f"📦 Exportando {os.path.basename(pt_path)} -> {backend} imgsz={imgsz} int8={int8}")
    out = YOLO(pt_path, task=task).export(**kw)
    print(f"✅ {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="openvino", choices=["openvino", "onnx", "ncnn"])
    ap.add_argument("--det-imgsz", default=os.getenv("DET_IMGSZ", "640"))
    ap.add_argument("--pose-imgsz", default=os.getenv("POSE_IMGSZ", "480"))
    ap.add_argument("--det-model", default=DET_PT)
    ap.add_argument("--pose-model", default=POSE_PT)
    ap.add_argument("--int8", action="store_true", help="quantização INT8 (exige --data com imagens de calibração)")
    ap.add_argument("--data", default=None, help="data.yaml do dataset para calibrar o INT8")
    a = ap.parse_args()

    if a.int8 and not a.data:
        ap.error("--int8 exige --data")

    export(a.det_model, "detect", parse_imgsz(a.det_imgsz), a.backend, a.int8, a.data)
    export(a.pose_model, "pose", parse_imgsz(a.pose_imgsz), a.backend, a.int8, a.data)