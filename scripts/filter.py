from pathlib import Path
import shutil

"""
    Script para mover pares de arquivos de label (.txt) e imagem (.jpg) de um diretório de origem para um diretório de destino.
    Ele garante que:
    - Apenas pares válidos de label e imagem sejam movidos.
    - Se o arquivo de imagem correspondente não existir, o label será ignorado.
"""

SRC_LABELS_DIR = Path("assets/modelo/active_learning/dataset_captura/Liora/Selecionar/labels")
SRC_IMAGES_DIR = Path("assets/modelo/active_learning/dataset_captura/Liora/Selecionar/images")

DST_LABELS_DIR = Path("assets/modelo/active_learning/dataset_captura/Liora/Selecionados-22-09/labels")
DST_IMAGES_DIR = Path("assets/modelo/active_learning/dataset_captura/Liora/Selecionados-22-09/images")

def mover_pares():
    # Cria as pastas de destino se não existirem
    DST_LABELS_DIR.mkdir(parents=True, exist_ok=True)
    DST_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Coleta todos os arquivos .txt
    txt_files = list(SRC_LABELS_DIR.glob("*.txt"))
    pares_movidos = 0

    for label_path in txt_files:
        stem = label_path.stem  # Nome do arquivo sem a extensão
        image_path = SRC_IMAGES_DIR / f"{stem}.jpg"

        # Verifica se o arquivo de imagem existe na pasta de origem
        if image_path.is_file():
            # Define os caminhos finais
            dst_label_path = DST_LABELS_DIR / label_path.name
            dst_image_path = DST_IMAGES_DIR / image_path.name

            # Move os arquivos (substitua shutil.move por shutil.copy2 se quiser apenas copiar)
            shutil.copy2(str(label_path), str(dst_label_path))
            shutil.copy2(str(image_path), str(dst_image_path))

            pares_movidos += 1
            print(f"[MOVIDO] {stem} (.txt e .jpg)")
        else:
            print(f"[IGNORADO] Imagem não encontrada para o label: {label_path.name}")

    print(f"\nConcluído! Total de pares movidos: {pares_movidos}")

if __name__ == "__main__":
    mover_pares()