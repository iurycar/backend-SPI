from pathlib import Path
import shutil
import random
import os

def split_dataset(
    src_images_dir: str,
    src_labels_dir: str,
    output_base_dir: str,
    targets: list[str],
    copy_files: bool = True
):
    src_img_path = Path(src_images_dir)
    src_lbl_path = Path(src_labels_dir)
    out_path = Path(output_base_dir)

    # Mapear arquivos .jpg e .txt existentes
    img_files = {p.stem: p for p in src_img_path.glob("*.jpg")}
    lbl_files = {p.stem: p for p in src_lbl_path.glob("*.txt")}

    # Identificar pares válidos (interseção pelo nome sem extensão)
    valid_stems = sorted(list(set(img_files.keys()) & set(lbl_files.keys())))
    
    total_pairs = len(valid_stems)
    num_targets = len(targets)

    if total_pairs == 0:
        print("Nenhum par correspondente (.jpg e .txt) foi encontrado.")
        return

    print(f"Total de pares válidos encontrados: {total_pairs}")
    print(f"Destinos ({num_targets}): {', '.join(targets)}")

    # Embaralhar aleatoriamente
    random.shuffle(valid_stems)

    # Calcular divisão
    base_count = total_pairs // num_targets
    remainder = total_pairs % num_targets
    
    # Distribuir entre as pastas
    start_idx = 0
    action_fn = shutil.copy2 if copy_files else shutil.move

    for i, target_name in enumerate(targets):
        # Distribui o resto para que a divisão seja o mais uniforme possível
        count = base_count + (1 if i < remainder else 0)
        end_idx = start_idx + count
        batch = valid_stems[start_idx:end_idx]
        start_idx = end_idx

        # Criar a estrutura de pastas
        dest_img_dir = out_path / target_name / "images"
        dest_lbl_dir = out_path / target_name / "labels"
        dest_img_dir.mkdir(parents=True, exist_ok=True)
        dest_lbl_dir.mkdir(parents=True, exist_ok=True)

        for stem in batch:
            action_fn(img_files[stem], dest_img_dir / f"{stem}.jpg")
            action_fn(lbl_files[stem], dest_lbl_dir / f"{stem}.txt")

        print(f"Pasta '{target_name}': {len(batch)} pares salvos.")

    print("\nDivisão concluída com sucesso!")

if __name__ == "__main__":
    PASTA_IMAGENS = "/home/iury/Downloads/dataset_captura_21_10/dataset_captura/images"
    PASTA_LABELS = "/home/iury/Downloads/dataset_captura_21_10/dataset_captura/labels"
    PASTA_DESTINO = "/home/iury/Downloads/dataset_captura_21_10/dataset"
    
    LISTA_DESTINATARIOS = ['bruno', 'iury', 'kethely', 'raissa', 'vanessa']

    split_dataset(
        src_images_dir=PASTA_IMAGENS,
        src_labels_dir=PASTA_LABELS,
        output_base_dir=PASTA_DESTINO,
        targets=LISTA_DESTINATARIOS,
        copy_files=True
    )
