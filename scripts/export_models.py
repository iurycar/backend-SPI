from ultralytics import YOLO
import argparse
import os

"""
Script utilitário para exportar modelos PyTorch (.pt) para formatos otimizados em CPU (OpenVINO, ONNX, NCNN).

Exemplos de uso:
    python scripts/export_models.py --backend openvino --det-imgsz 640 --pose-imgsz 480
    python scripts/export_models.py --backend openvino --det-imgsz 384,640 --pose-imgsz 384,480
    python scripts/export_models.py --backend onnx
"""

DIRETORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_MODELO_DETECCAO_PT = os.path.join(DIRETORIO_RAIZ, "assets", "modelo", "treinamento", "best.pt")
CAMINHO_MODELO_POSE_PT = os.path.join(DIRETORIO_RAIZ, "assets", "modelo", "treinamento", "yolov8m-pose.pt")


def converter_dimensao_imagem(texto: str):
    """Converte entradas como '640' ou '384,640' em inteiros utilizáveis pelo YOLO."""
    partes = [int(x) for x in texto.replace("x", ",").split(",") if x.strip()]
    return partes[0] if len(partes) == 1 else partes


def exportar_modelo(caminho_pt: str, tarefa: str, dimensao_img, backend: str, quantizar_int8: bool, caminho_dados: str):
    """Executa a exportação do modelo YOLO para o formato especificado."""
    if not os.path.exists(caminho_pt):
        print(f"⚠️  {caminho_pt} não encontrado — pulando.")
        return

    parametros = dict(
        format=backend, 
        imgsz=dimensao_img, 
        half=False, 
        dynamic=False, 
        batch=1
    )

    if backend == "onnx":
        parametros["simplify"] = True

    if backend == "openvino" and quantizar_int8:
        parametros.update(int8=True, data=caminho_dados)

    print(f"📦 Iniciando exportação: {os.path.basename(caminho_pt)} -> {backend.upper()} (imgsz={dimensao_img}, int8={quantizar_int8})")
    saida = YOLO(caminho_pt, task=tarefa).export(**parametros)
    print(f"✅ Exportação concluída com sucesso: {saida}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exporta modelos YOLO para backends acelerados.")
    parser.add_argument(
        "--backend",
        default="openvino",
        choices=["openvino", "onnx", "ncnn"],
        help="Backend de inferência desejado (padrão: openvino).",
    )
    parser.add_argument(
        "--det-imgsz",
        default=os.getenv("DET_IMGSZ", "640"),
        help="Tamanho da imagem para o modelo de detecção de EPI (ex: 640 ou 384,640).",
    )
    parser.add_argument(
        "--pose-imgsz",
        default=os.getenv("POSE_IMGSZ", "480"),
        help="Tamanho da imagem para o modelo de postura (ex: 480 ou 384,480).",
    )
    parser.add_argument(
        "--det-model",
        default=CAMINHO_MODELO_DETECCAO_PT,
        help="Caminho do arquivo .pt do modelo de detecção.",
    )
    parser.add_argument(
        "--pose-model",
        default=CAMINHO_MODELO_POSE_PT,
        help="Caminho do arquivo .pt do modelo de postura.",
    )
    parser.add_argument(
        "--int8",
        action="store_true",
        help="Habilita quantização INT8 (requer informar --data com o arquivo data.yaml de calibração).",
    )
    parser.add_argument(
        "--data",
        default=None,
        help="Caminho do arquivo dataset data.yaml necessário para calibração INT8.",
    )

    argumentos = parser.parse_args()

    if argumentos.int8 and not argumentos.data:
        parser.error("A quantização INT8 requer o parâmetro --data apontando para o arquivo data.yaml do dataset.")

    # Exporta o modelo de detecção de EPIs
    exportar_modelo(
        caminho_pt=argumentos.det_model,
        tarefa="detect",
        dimensao_img=converter_dimensao_imagem(argumentos.det_imgsz),
        backend=argumentos.backend,
        quantizar_int8=argumentos.int8,
        caminho_dados=argumentos.data,
    )

    # Exporta o modelo de estimativa de postura
    exportar_modelo(
        caminho_pt=argumentos.pose_model,
        tarefa="pose",
        dimensao_img=converter_dimensao_imagem(argumentos.pose_imgsz),
        backend=argumentos.backend,
        quantizar_int8=argumentos.int8,
        caminho_dados=argumentos.data,
    )