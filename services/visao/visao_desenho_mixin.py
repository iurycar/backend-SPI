import numpy as np
import time
import cv2

"""
    Mixin para estilização, renderização de badges, caixas delimitadoras e esqueletos de pose.
"""

class VisaoDesenhoMixin:
    CORES = {
        "verde": (0, 255, 0),
        "vermelho": (0, 0, 255),
        "azul": (255, 0, 0),
        "amarelo": (0, 255, 255),
        "ciano": (255, 255, 0),
        "magenta": (255, 0, 255),
        "cinza": (120, 120, 120),
        "branco": (255, 255, 255),
    }

    ESQUELETO_CONEXOES = [
        (0, 1), (0, 2), (1, 3), (2, 4),
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12),
        (11, 13), (13, 15), (12, 14), (14, 16),
    ]

    TEMPO_MAXIMO_OVERLAY = 1.5

    def _desenhar_caixa(self, frame, x1, y1, x2, y2, cor=(0, 255, 0), espessura=2, comprimento=12):
        """Desenha cantos reforçados para destacar as caixas delimitadoras."""

        largura = max(0, x2 - x1)
        altura = max(0, y2 - y1)

        comp_x = min(comprimento, largura // 2)
        comp_y = min(comprimento, altura // 2)

        if comp_x <= 0 or comp_y <= 0:
            return

        cv2.line(frame, (x1, y1), (x1 + comp_x, y1), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x1, y1), (x1, y1 + comp_y), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x2, y1), (x2 - comp_x, y1), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x2, y1), (x2, y1 + comp_y), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x1, y2), (x1 + comp_x, y2), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x1, y2), (x1, y2 - comp_y), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x2, y2), (x2 - comp_x, y2), cor, espessura, cv2.LINE_AA)
        cv2.line(frame, (x2, y2), (x2, y2 - comp_y), cor, espessura, cv2.LINE_AA)

    def _desenhar_caixa_delimitadora(self, frame, caixa, label, cor=(0, 210, 255)):
        """Desenha caixas delimitadoras protegidas contra coordenadas fora do limite da imagem."""
        altura_img, largura_img = frame.shape[:2]

        x1 = int(np.clip(caixa[0], 0, largura_img - 1))
        y1 = int(np.clip(caixa[1], 0, altura_img - 1))
        x2 = int(np.clip(caixa[2], 0, largura_img - 1))
        y2 = int(np.clip(caixa[3], 0, altura_img - 1))
        
        if x2 <= x1 or y2 <= y1:
            return

        cv2.rectangle(frame, (x1, y1), (x2, y2), cor, 1, cv2.LINE_AA)
        self._desenhar_caixa(frame, x1, y1, x2, y2, cor, espessura=2, comprimento=14)

        fonte = cv2.FONT_HERSHEY_DUPLEX
        escala = 0.45
        espessura_txt = 1
        (largura_txt, altura_txt), _ = cv2.getTextSize(label, fonte, escala, espessura_txt)

        preenchimento = 4
        badge_altura = altura_txt + (preenchimento * 2)
        badge_largura = largura_txt + (preenchimento * 2)

        if y1 - badge_altura >= 0:
            b_y1 = y1 - badge_altura
            b_y2 = y1
            txt_y = y1 - preenchimento - 1
        else:
            b_y1 = y1
            b_y2 = min(altura_img, y1 + badge_altura)
            txt_y = y1 + altura_txt + preenchimento

        b_x1 = x1
        b_x2 = min(largura_img, x1 + badge_largura)
        txt_x = x1 + preenchimento

        cv2.rectangle(frame, (b_x1, b_y1), (b_x2, b_y2), cor, -1)
        cv2.putText(frame, label, (txt_x, txt_y), fonte, escala, (15, 15, 15), espessura_txt, cv2.LINE_AA)

    def desenhar_overlay(self, imagem, overlay: dict, escala: float) -> None:
        """Renderiza os resultados mais recentes no frame que será transmitido via streaming."""
        agora = time.monotonic()

        # Desenha as caixas de EPI e pessoas
        if agora - overlay.get("det_tempo", 0.0) < self.TEMPO_MAXIMO_OVERLAY:
            for _, xyxy, rotulo, cor in overlay.get("det", ()):
                caixa = [int(valor * escala) for valor in xyxy]
                self._desenhar_caixa_delimitadora(imagem, caixa, rotulo, self.CORES.get(cor, (0, 255, 0)))

        # Desenha o esqueleto de pose
        if agora - overlay.get("pose_tempo", 0.0) < self.TEMPO_MAXIMO_OVERLAY:
            for pessoa in overlay.get("pose", ()):
                pontos = [(int(x * escala), int(y * escala)) for x, y in pessoa["pontos"]]
                confs = pessoa.get("confs", [1.0] * len(pontos))

                # Desenha apenas keypoints visíveis
                for (x, y), conf in zip(pontos, confs):
                    if x > 0 and y > 0 and conf >= 0.5:
                        cv2.circle(imagem, (x, y), 4, (0, 255, 180), -1, cv2.LINE_AA)
                        cv2.circle(imagem, (x, y), 5, (20, 20, 20), 1, cv2.LINE_AA)

                # Desenha apenas conexões onde ambos os pontos possuem confiança suficiente
                for p1, p2 in self.ESQUELETO_CONEXOES:
                    x1, y1 = pontos[p1]
                    x2, y2 = pontos[p2]
                    if (x1 > 0 and y1 > 0 and confs[p1] >= 0.5) and (x2 > 0 and y2 > 0 and confs[p2] >= 0.5):
                        cv2.line(imagem, (x1, y1), (x2, y2), (255, 180, 0), 2, cv2.LINE_AA)

                # Desenha a coluna apenas se válida
                if pessoa.get("coluna") is not None:
                    p_ombro, p_quadril = pessoa["coluna"]
                    cv2.line(
                        imagem,
                        (int(p_ombro[0] * escala), int(p_ombro[1] * escala)),
                        (int(p_quadril[0] * escala), int(p_quadril[1] * escala)),
                        self.CORES.get(pessoa.get("cor", "ciano"), (255, 255, 0)),
                        4,
                        cv2.LINE_AA,
                    )