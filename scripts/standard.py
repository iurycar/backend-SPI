import os
from pathlib import Path

"""
    Script para remapear os IDs das classes nos arquivos de label (.txt) do dataset.
    Ele garante que:
    - Apenas os IDs de classe especificados no dicionário CLASS_MAPPING sejam mantidos.
    - As linhas com IDs de classe não mapeados sejam removidas.
"""

# Mapeamento: {id_origem: id_destino}
# IDs de origem ausentes no dicionário serão descartados.
CLASS_MAPPING = {
    0: 1,   # hand_glove    -> Com_luva
    1: 6,   # hand_noglove  -> Sem_luva
}

CLASSES = {
    0: "Pessoa",
    1: "Com_luva",
    2: "Com_oculos",
    3: "Com_capacete",
    4: "Com_oculos_normal",
    5: "Com_mascara",
    6: "Sem_luva",
    7: "Sem_oculos",
    8: "Sem_capacete",
    9: "Sem_mascara",
    10: "Com_colete",
    11: "Sem_colete",
    12: "Com_chapeu"
}

# Determinar o redimensionamento das caixas delimitadoras para classes específicas
CLASS_RESIZE = {
    6: 20,
    1: 20,
    5: -5,
}

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".PNG"]

def adjust_bbox(x: float, y: float, width: float, height: float, scale_pct: float):
    factor = 1.0 + (scale_pct / 100.0)
    new_w = width * factor
    new_h = height * factor
    
    # Clamping para manter a caixa válida dentro da imagem [0.0, 1.0]
    new_w = max(0.001, min(1.0, new_w))
    new_h = max(0.001, min(1.0, new_h))
    
    return x, y, new_w, new_h

def find_associated_image(label_path: Path):
    stem = label_path.stem
    
    # Procura imagem no mesmo diretório do .txt
    for ext in IMAGE_EXTENSIONS:
        img_path = label_path.with_suffix(ext)
        if img_path.is_file():
            return img_path

    parts = list(label_path.parts)
    if "labels" in parts:
        # Substitui a última ocorrência de 'labels' por 'images'
        idx = len(parts) - 1 - parts[::-1].index("labels")
        
        parts[idx] = "images"
        
        images_dir = Path(*parts).parent

        for ext in IMAGE_EXTENSIONS:
            img_path = images_dir / f"{stem}{ext}"
            if img_path.is_file():
                return img_path

    return None

def process_dataset(labels_dir: str):
    labels_path = Path(labels_dir)
    txt_files = list(labels_path.rglob("*.txt"))

    total_lines = 0
    kept_lines = 0
    removed_lines = 0
    deleted_files_count = 0

    for file_path in txt_files:
        new_lines = []
        
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                
                parts = stripped.split()
                total_lines += 1
                
                try:
                    src_cls = int(parts[0])
                    coords = [float(v) for v in parts[1:5]]
                except (ValueError, IndexError):
                    removed_lines += 1
                    continue

                if src_cls in CLASS_MAPPING:
                    target_cls = CLASS_MAPPING[src_cls]
                    x, y, w, h = coords
                    
                    # Aplica redimensionamento se a classe estiver configurada
                    if target_cls in CLASS_RESIZE:
                        scale = CLASS_RESIZE[target_cls]
                        x, y, w, h = adjust_bbox(x, y, w, h, scale)
                    
                    # Formata linha no padrão YOLO: <class> <x> <y> <w> <h> [extras...]
                    new_line_parts = [str(target_cls), f"{x:.6f}", f"{y:.6f}", f"{w:.6f}", f"{h:.6f}"]
                    if len(parts) > 5:
                        new_line_parts.extend(parts[5:])  # Preserva keypoints/segmentação se houver
                        
                    new_lines.append(" ".join(new_line_parts) + "\n")
                    kept_lines += 1
                else:
                    removed_lines += 1

        # Se não sobrou nenhuma anotação de interesse, remove label e imagem
        if not new_lines:
            img_file = find_associated_image(file_path)
            if img_file and img_file.exists():
                img_file.unlink()
            
            file_path.unlink()
            deleted_files_count += 1
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

    print("Processamento concluído.")
    print(f"Total de arquivos .txt verificados: {len(txt_files)}")
    print(f"Arquivos/amostras sem interesse deletados: {deleted_files_count}")
    print(f"Linhas mantidas/convertidas:        {kept_lines}")
    print(f"Linhas removidas:                   {removed_lines}")

if __name__ == "__main__":
    # Altere para a pasta onde estão os labels (ex: 'dataset/train/labels' ou a pasta raiz)
    caminho_labels = "/home/iury/Downloads/Glove_detection.v3i.yolov8/train/labels"
    process_dataset(caminho_labels)