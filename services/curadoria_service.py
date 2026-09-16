from services.augmentation_service import AugmentationService
from schemas.config_dto import ConfigDTO
from pathlib import Path
import random
import shutil
import yaml
import os
import re

BASE_DIR = Path(__file__).resolve().parent.parent

CURRENT_CONFIG = {
    "source_dir": os.path.join(BASE_DIR, "assets/modelo/active_learning/dataset_captura"),
    "target_dir": os.path.join(BASE_DIR, "assets/modelo/active_learning/dataset_tratado")
}

class CuradoriaService:
    def __init__(self):
        self.augmentation_service = AugmentationService()
        self.class_names = {}
        # Memória para armazenar o timestamp da última imagem processada e o destino da última imagem processada
        self.timestamp_last_image = None
        self.dest_last_image = None

        self.config_path = os.path.join(BASE_DIR, "assets", "config.yaml")

        self.load_config()  # Carrega a configuração do arquivo YAML, se existir

        self.src_imgs, self.src_lbls = self.get_source_paths()
        self.tgt_train_imgs, self.tgt_train_lbls, self.tgt_val_imgs, self.tgt_val_lbls = self.get_target_paths()


    def load_config(self):
        """Carrega a configuração do arquivo YAML, se existir."""

        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f)
                # Configura os caminhos de origem e destino com base no arquivo YAML
                CURRENT_CONFIG["source_dir"] = data.get("path_captured", CURRENT_CONFIG["source_dir"])
                CURRENT_CONFIG["target_dir"] = data.get("path_cured", CURRENT_CONFIG["target_dir"])

                self.class_names.update(data.get("classes", {}))

    @staticmethod
    def get_source_paths() -> tuple[str, str]:
        """Retorna os caminhos de origem (images/ e labels/) da configuração atual."""
        src = CURRENT_CONFIG["source_dir"]
        return os.path.join(src, "images"), os.path.join(src, "labels")

    @staticmethod
    def get_target_paths() -> tuple[str, str, str, str]:
        tgt = CURRENT_CONFIG["target_dir"]
        path_train_images = os.path.join(tgt, "train", "images")
        path_train_labels = os.path.join(tgt, "train", "labels")
        path_val_images = os.path.join(tgt, "val", "images")
        path_val_labels = os.path.join(tgt, "val", "labels")

        return path_train_images, path_train_labels, path_val_images, path_val_labels

    def extrair_timestamp(self, filename_or_path: str) -> float:
        """Extrai timestamp em segundos do nome do arquivo (ex: frame_al_1789131718074.jpg) ou do mtime."""

        # Primeiro, tenta extrair um número de 10 a 13 dígitos do nome do arquivo
        match = re.search(r'(\d{10,13})', filename_or_path)
        if match:
            val = int(match.group(1)) # Converte para inteiro
            return val / 1000.0 if val > 1e10 else float(val) # Se for timestamp em milissegundos, converte para segundos

        # Se não houver número no nome do arquivo, retorna o mtime do arquivo, se existir
        if os.path.exists(filename_or_path):
            return os.path.getmtime(filename_or_path)

        return 0.0

    def obter_configuracao(self) -> dict:
        return CURRENT_CONFIG

    def obter_classes(self) -> dict:
        classes = []
        for class_id, class_name in self.class_names.items():
            classes.append({'id': class_id, 'name': class_name})

        print(f"Classes obtidas: {classes}")
        return classes

    def obter_imagens_total(self) -> int | dict:
        img_dir, lbl_dir = self.get_source_paths()

        if not os.path.exists(img_dir):
            return 0

        valid_ext = ('.jpg', '.jpeg', '.png')
        total = 0

        try:
            for nome_arquivo in os.scandir(img_dir):
                if nome_arquivo.is_file() and nome_arquivo.name.lower().endswith(valid_ext):
                    base_name = os.path.splitext(nome_arquivo.name)[0]
                    label_path = os.path.join(lbl_dir, f"{base_name}.txt")

                    if os.path.exists(label_path):
                        total += 1
        except Exception as e:
            return {"error": f"Erro ao contar imagens: {str(e)}"}

        return total

    def obter_imagens_lote(self, inicio: int, fim: int) -> list[dict]:
        img_dir, lbl_dir = self.get_source_paths()

        if not os.path.exists(img_dir):
            return []

        valid_extensions = ('.jpg', '.jpeg', '.png')
        imagens = []

        arquivos = []
        for arquivo in os.listdir(img_dir):
            if arquivo.lower().endswith(valid_extensions):
                arquivos.append(arquivo)

        arquivos = sorted(arquivos)

        inicio_idx = max(0, inicio - 1)
        fim_idx = max(inicio_idx, fim)
        lote_arquivos = arquivos[inicio_idx:fim_idx]

        imagens = []
        for nome_arquivo in lote_arquivos:
            nome_base = os.path.splitext(nome_arquivo)[0]
            arquivo_lbl = f"{nome_base}.txt"
            caminho_lbl = os.path.join(lbl_dir, arquivo_lbl)

            if os.path.exists(caminho_lbl):
                imagens.append({
                    'id': nome_base,
                    'image_file': nome_arquivo,
                    'label_file': arquivo_lbl
                }) 

        return imagens

    def obter_imagem(self, nome_arquivo: str) -> str:
        img_dir, _ = self.get_source_paths()

        caminho_imagem = os.path.join(img_dir, nome_arquivo)

        if not os.path.exists(caminho_imagem):
            return None

        return caminho_imagem

    def obter_labels(self, nome_arquivo: str) -> str | None:
        _, lbl_dir = self.get_source_paths()

        caminho_label = os.path.join(lbl_dir, nome_arquivo)

        if not os.path.exists(caminho_label):
            return []

        boxes = []

        with open(caminho_label, 'r') as f:
            for i, linha in enumerate(f.readlines()):
                linha_str = linha.strip()

                if not linha_str:
                    continue

                conf_valor = None

                if ':' in linha_str:
                    partes_coords, partes_conf = linha_str.split(':', 1)
                    coords = partes_coords.strip().split()

                    try:
                        conf_valor = float(partes_conf.strip())
                    except ValueError:
                        conf_valor = None
                else:
                    coords = linha_str.split()

                if len(coords) >= 5:
                    cls_id = int(coords[0])

                    boxes.append({
                        'box_id': i,
                        'class_id': cls_id,
                        'class_name': self.class_names.get(cls_id, f"Classe {cls_id}"),
                        'x_center': float(coords[1]),
                        'y_center': float(coords[2]),
                        'width': float(coords[3]),
                        'height': float(coords[4]),
                        'confidence': conf_valor,
                        'valid': True
                    })

        return boxes

    def salvar_e_mover(
            self, 
            nome_arquivo: str, 
            arquivo_imagem: str, 
            arquivo_label: str, 
            boxes: list[dict], 
            aplicar_aug: bool = False, 
            val_split: bool = False, 
            split: str = None
        ) -> dict:

        src_img_dir, src_lbl_dir = self.get_source_paths()
        tgt_train_imgs, tgt_train_lbls, tgt_val_imgs, tgt_val_lbls = self.get_target_paths()

        for path in (tgt_train_imgs, tgt_train_lbls, tgt_val_imgs, tgt_val_lbls):
            os.makedirs(path, exist_ok=True)

        src_img: str = os.path.join(src_img_dir, arquivo_imagem)
        src_lbl: str = os.path.join(src_lbl_dir, arquivo_label)

        current_timestamp = self.extrair_timestamp(src_img)

        if val_split and split not in ['train', 'val']:
            if (self.timestamp_last_image is not None and self.dest_last_image is not None and abs(current_timestamp - self.timestamp_last_image) < 60):
                _split = self.dest_last_image
            else:
                _split = 'val' if random.randint(1, 100) <= 20 else 'train'
        else:
            if split not in ['train', 'val']:
                _split = 'train'
            else:
                _split = split

        self.timestamp_last_image = current_timestamp
        self.dest_last_image = _split
        is_val = (_split == 'val')

        if is_val:
            print(f"🖎 Movendo {arquivo_imagem} para validação.")
            dest_img = os.path.join(tgt_val_imgs, arquivo_imagem)
            dest_lbl = os.path.join(tgt_val_lbls, arquivo_label)
        else:
            dest_img = os.path.join(tgt_train_imgs, arquivo_imagem)
            dest_lbl = os.path.join(tgt_train_lbls, arquivo_label)

        boxes_validas: list[dict] = []
        linhas: list[str] = []
        for box in boxes:
            valida = box.get('valid', True)
            if valida:
                boxes_validas.append(box)

        for box in boxes_validas:
            cls_id = box['class_id']
            xc = max(0.0, min(1.0, float(box["x_center"])))
            yc = max(0.0, min(1.0, float(box["y_center"])))
            w = max(0.0, min(1.0, float(box["width"])))
            h = max(0.0, min(1.0, float(box["height"])))
            linhas.append(f"{cls_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

        with open(dest_lbl, 'w') as f:
            f.write("\n".join(linhas))

        if os.path.exists(src_img):
            shutil.move(src_img, dest_img)

        if os.path.exists(src_lbl):
            os.remove(src_lbl)

        if not is_val and aplicar_aug:
            self.augmentation_service.gererate_augmented_copies(
                img_path=dest_img,
                boxes=boxes_validas,
                dir_output_img=tgt_train_imgs,
                dir_output_lbl=tgt_train_lbls,
                base_name=nome_arquivo
            )

        return {
            "status": "sucesso",
            "split": _split,
        }

    def deletar_imagem(self, nome_arquivo: str):
        scr_img_dir, scr_lbl_dir = self.get_source_paths()
        caminho_lbl = os.path.join(scr_lbl_dir, f"{nome_arquivo}.txt")

        for ext in ['.jpg', '.jpeg', '.png']:
            caminho_img = os.path.join(scr_img_dir, f"{nome_arquivo}{ext}")
            if os.path.exists(caminho_img):
                os.remove(caminho_img)
                break

        if os.path.exists(caminho_lbl):
            os.remove(caminho_lbl)

        return {"status": "removido"}

    def atualizar_configuracao(self, nova_config: ConfigDTO) -> dict:
        CURRENT_CONFIG['source_dir'] = nova_config.source_dir
        CURRENT_CONFIG['target_dir'] = nova_config.target_dir

        if nova_config.classes is not None or nova_config.classes != []:
            for idx, class_name in enumerate(nova_config.classes):
                self.class_names[idx] = class_name

        tgt_train_imgs, tgt_train_lbls, tgt_val_imgs, tgt_val_lbls = self.get_target_paths()
        for path in (tgt_train_imgs, tgt_train_lbls, tgt_val_imgs, tgt_val_lbls):
            os.makedirs(path, exist_ok=True)

        # Salva no arquivo YAML
        config_data = {
            "path_captured": nova_config.source_dir,
            "path_cured": nova_config.target_dir,
            "classes": nova_config.classes
        }

        with open("config.yaml", "w") as f:
            yaml.dump(config_data, f)

        return CURRENT_CONFIG
