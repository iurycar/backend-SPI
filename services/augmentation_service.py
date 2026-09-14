import albumentations as Album
import cv2
import os

class AugmentationService:
    def __init__(self):
        self.augmentation = {
            # Simulação de baixa taxa de bits e compressão RTSP
            "compression_artifacts": Album.Compose([
                Album.ImageCompression(quality_range=(30, 60), p=1.0),
                Album.Downscale(scale_range=(0.5, 0.75), p=1.0)
            ]),

            # Ruído de ganho ISO e granulação de sensor
            "sensor_iso_noise": Album.Compose([
                Album.ISONoise(color_shift=(0.02, 0.08), intensity=(0.2, 0.6), p=1.0),
                Album.MultiplicativeNoise(multiplier=(0.9, 1.1), elementwise=True, p=1.0)
            ]),

            # Desfoque de movimento direcional (ângulo no padrão válido 0 a 360)
            "motion_blur": Album.Compose([
                Album.MotionBlur(blur_limit=(7, 15), angle_range=(0, 90), p=1.0)
            ]),

            # Equalização adaptativa local (sombras e clarões)
            "clahe_contrast": Album.Compose([
                Album.CLAHE(clip_limit=4.0, tile_grid_size=(8, 8), p=1.0)
            ]),

            # Distorção óptica (única que altera a geometria e precisa de bbox_params)
            "lens_distortion": Album.Compose([
                Album.OpticalDistortion(distort_limit=0.2, border_mode=cv2.BORDER_REFLECT, p=1.0)
            ], bbox_params=Album.BboxParams(format='yolo', label_fields=['category_ids'], min_visibility=0.4))
        }

    def gererate_augmented_copies(self, img_path: str, boxes: list, dir_output_img: str, dir_output_lbl: str, base_name: str, target_classes=None):
        if not os.path.exists(img_path):
            raise FileNotFoundError(f"Imagem não encontrada: {img_path}")

        # Validação correta de target_classes (usando conjuntos)
        if target_classes is not None:
            present_classes = {int(box['class_id']) for box in boxes}
            if not present_classes.intersection(set(target_classes)):
                return

        imagem = cv2.imread(img_path)
        if imagem is None:
            print(f"Erro ao carregar a imagem: {img_path}")
            return

        yolo_bboxes = []
        category_ids = []
        for box in boxes:
            x_c = max(0.001, min(0.999, float(box['x_center'])))
            y_c = max(0.001, min(0.999, float(box['y_center'])))
            largura = max(0.001, min(0.999, float(box['width'])))
            altura = max(0.001, min(0.999, float(box['height'])))

            # Evita caixas transbordando as bordas [0, 1]
            if x_c - (largura / 2) < 0:
                largura = 2 * x_c
            if x_c + (largura / 2) > 1:
                largura = 2 * (1.0 - x_c)
            if y_c - (altura / 2) < 0:
                altura = 2 * y_c
            if y_c + (altura / 2) > 1:
                altura = 2 * (1.0 - y_c)

            yolo_bboxes.append([x_c, y_c, largura, altura])
            category_ids.append(int(box['class_id']))

        for sufixo, transformacao in self.augmentation.items():
            try:
                # Envia bboxes apenas se o pipeline contiver o processador de coordenadas
                if transformacao.processors.get('bboxes'):
                    transformada = transformacao(image=imagem, bboxes=yolo_bboxes, category_ids=category_ids)
                    aug_bboxes = transformada['bboxes']
                    aug_labels = transformada['category_ids']
                else:
                    transformada = transformacao(image=imagem)
                    aug_bboxes = yolo_bboxes
                    aug_labels = category_ids

                img_aug = transformada['image']

                if len(yolo_bboxes) > 0 and len(aug_bboxes) == 0:
                    print(f"Transformação '{sufixo}' removeu todas as bounding boxes. Pulando...")
                    continue

                aug_base_name = f"{base_name}_{sufixo}"
                dest_img = os.path.join(dir_output_img, f"{aug_base_name}.jpg")
                dest_lbl = os.path.join(dir_output_lbl, f"{aug_base_name}.txt")

                cv2.imwrite(dest_img, img_aug)

                lines = []
                for bbox, cls_id in zip(aug_bboxes, aug_labels):
                    x_c, y_c, largura, altura = bbox
                    lines.append(f"{int(cls_id)} {x_c:.6f} {y_c:.6f} {largura:.6f} {altura:.6f}")
    
                with open(dest_lbl, 'w') as file:
                    file.write("\n".join(lines))

            except Exception as e:
                print(f"[Augmentation] Falha ao processar '{sufixo}' em '{base_name}': {e}")