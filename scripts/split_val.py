import random
import shutil
from pathlib import Path

"""
    Script para separar uma porcentagem do dataset de treino para validação.
    Ele garante que:
    - Nenhuma imagem com sufixo de augmentation seja selecionada para validação.
    - Nenhuma imagem original seja selecionada se houver qualquer variante aumentada dela no dataset.
    - Apenas pares válidos de imagem e label (.txt) sejam considerados.
"""

DATASET_DIR = Path("assets/modelo/active_learning/dataset_tratado")
SRC_IMAGES_DIR = DATASET_DIR / "train" / "images"
SRC_LABELS_DIR = DATASET_DIR / "train" / "labels"

VAL_IMAGES_DIR = DATASET_DIR / "val" / "images"
VAL_LABELS_DIR = DATASET_DIR / "val" / "labels"

VAL_RATIO = 0.15
RANDOM_SEED = 42

# Lista completa de todas as transformações de augmentation usadas no projeto
AUGMENTATION_SUFFIXES = [
    "_clahe_contrast",
    "_compression_artifacts",
    "_motion_blur",
    "_sensor_iso_noise",
    "_lens_distortion",
    "_color_jitter",
    "_gaussian_blur",
    "_rotation",
]

def split_validation():
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    VAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    VAL_LABELS_DIR.mkdir(parents=True, exist_ok=True)

    # Coleta todas as imagens do diretório de treino
    image_extensions = ("*.jpg", "*.jpeg", "*.png")
    all_images = []
    for ext in image_extensions:
        all_images.extend(SRC_IMAGES_DIR.glob(ext))

    all_stems = {img.stem for img in all_images}

    valid_pairs = []

    for img_path in all_images:
        stem = img_path.stem

        # Ignora se o nome da imagem contiver ou terminar com qualquer sufixo de augmentation
        if any(stem.endswith(suf) for suf in AUGMENTATION_SUFFIXES):
            continue

        # Ignora a imagem original se existir QUALQUER variante aumentada dela no dataset
        # Ex: se existir 'frame_000300_lens_distortion', a 'frame_000300' é rejeitada
        has_augmented_variant = any(f"{stem}{suf}" in all_stems for suf in AUGMENTATION_SUFFIXES)
        if has_augmented_variant:
            continue

        # Só é válida se tiver o label .txt correspondente
        lbl_path = SRC_LABELS_DIR / f"{stem}.txt"
        if not lbl_path.is_file():
            continue

        valid_pairs.append((lbl_path, img_path))

    total_valid = len(valid_pairs)
    print(f"Total de pares candidatos para validação: {total_valid}")

    if total_valid == 0:
        print("Nenhum par elegível encontrado. Verifique se todas as imagens originais geraram augmentations.")
        return

    val_count = int(total_valid * VAL_RATIO)
    print(f"Separando {val_count} pares ({VAL_RATIO * 100:.0f}%) para validação...")

    val_selected = random.sample(valid_pairs, val_count)

    for lbl_path, img_path in val_selected:
        dst_img = VAL_IMAGES_DIR / img_path.name
        dst_lbl = VAL_LABELS_DIR / lbl_path.name

        shutil.move(str(img_path), str(dst_img))
        shutil.move(str(lbl_path), str(dst_lbl))

    remaining_train_images = sum(len(list(SRC_IMAGES_DIR.glob(ext))) for ext in image_extensions)
    print("\nDivisão concluída com sucesso!")
    print(f"- Validação: {val_count} amostras em {VAL_IMAGES_DIR.parent}")
    print(f"- Imagens restantes em treino: {remaining_train_images}")


if __name__ == "__main__":
    split_validation()