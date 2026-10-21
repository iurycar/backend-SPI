from pathlib import Path
from collections import Counter
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def count_classes_yolo(labels_dir: str | Path, yaml_path: str | Path | None = None):
    labels_path = Path(labels_dir)
    if not labels_path.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {labels_path.resolve()}")

    class_names = {}
    if yaml_path and Path(yaml_path).exists():
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            names = data.get('names', {})

            if isinstance(names, list):
                class_names = {idx: name for idx, name in enumerate(names)}
            elif isinstance(names, dict):
                class_names = {int(k): v for k, v in names.items()}

    class_counts = Counter()
    total_annotations = 0
    total_files = 0
    empty_files = 0

    for txt_file in labels_path.rglob("*.txt"):
        if txt_file.name in ("classes.txt", "train.txt", "val.txt", "test.txt"):
            continue

        total_files += 1
        with open(txt_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            empty_files += 1
            continue

        for line in lines:
            parts = line.split()
            try:
                class_id = int(parts[0])
                class_counts[class_id] += 1
                total_annotations += 1
            except (ValueError, IndexError):
                continue

    print("\n" + "=" * 45)
    print(f" RESUMO DO DATASET: {labels_path.name}")
    print("=" * 45)
    print(f"Arquivos .txt processados: {total_files}")
    print(f"Arquivos sem objetos:     {empty_files}")
    print(f"Total de anotações (bbox): {total_annotations}")
    print("-" * 45)
    print(f"{'ID':<6} | {'Classe':<20} | {'Qtd':<10} | {'%':<6}")
    print("-" * 45)

    for class_id in sorted(class_counts.keys()):
        count = class_counts[class_id]
        name = class_names.get(class_id, f"class_{class_id}")
        pct = (count / total_annotations * 100) if total_annotations > 0 else 0
        print(f"{class_id:<6} | {name:<20} | {count:<10} | {pct:>5.1f}%")

    print("=" * 45 + "\n")
    return class_counts

if __name__ == "__main__":
    LABELS_DIRECTORY = PROJECT_ROOT / "assets/modelo/active_learning/dataset_tratado/train/labels"
    YAML_FILE = PROJECT_ROOT / "assets/modelo/data.yaml"

    count_classes_yolo(LABELS_DIRECTORY, YAML_FILE)