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
    0: 3,   # helmet     -> Com_capacete
    1: 1,   # gloves     -> Com_luva
    2: 10,  # vest       -> Com_colete
    4: 2,   # goggles    -> Com_oculos
    6: 0,   # Person     -> Pessoa
    7: 8,   # no_helmet  -> Sem_capacete
    8: 7,   # no_goggle  -> Sem_oculos
    9: 6,   # no_gloves  -> Sem_luva
}

def remap_labels(labels_dir: str):
    labels_path = Path(labels_dir)
    txt_files = list(labels_path.rglob("*.txt"))

    total_lines = 0
    kept_lines = 0
    removed_lines = 0

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
                except ValueError:
                    # Linha mal formatada ou cabeçalho
                    removed_lines += 1
                    continue

                if src_cls in CLASS_MAPPING:
                    target_cls = CLASS_MAPPING[src_cls]
                    parts[0] = str(target_cls)
                    new_lines.append(" ".join(parts) + "\n")
                    kept_lines += 1
                else:
                    removed_lines += 1

        # Sobrescreve o arquivo com as anotações filtradas e convertidas
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    print("Processamento concluído.")
    print(f"Total de arquivos processados: {len(txt_files)}")
    print(f"Linhas mantidas/convertidas:   {kept_lines}")
    print(f"Linhas removidas:              {removed_lines}")

if __name__ == "__main__":
    # Altere para a pasta onde estão os labels (ex: 'dataset/train/labels' ou a pasta raiz)
    caminho_labels = "/home/iury/Downloads/construction-ppe/images/train/labels"
    remap_labels(caminho_labels)