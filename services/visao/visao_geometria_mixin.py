import numpy as np
import cv2

"""
    Mixin para cálculos geométricos e conversão de coordenadas de regiões e bounding boxes.
"""

class VisaoGeometriaMixin:
    def regiao_para_pixels(self, regiao, img_largura: int, img_altura: int) -> list[tuple[int, int]]:
        """Converte as coordenadas da região (normalizada 0.0..1.0 ou absoluta) para pixels na imagem."""

        if not regiao:
            return []

        max_valor = max(max(abs(float(ponto[0])), abs(float(ponto[1]))) for ponto in regiao)
        if max_valor <= 1.0:
            return [
                (int(float(ponto[0]) * img_largura), int(float(ponto[1]) * img_altura))
                for ponto in regiao
            ]

        return [
            (int(float(ponto[0])), int(float(ponto[1])))
            for ponto in regiao
        ]

    def normalizar_regiao(self, regiao, img_largura: int, img_altura: int) -> list[tuple[float, float]]:
        """Garante que as coordenadas dos pontos fiquem normalizadas entre 0.0 e 1.0."""

        if not regiao:
            return []

        max_val = max(max(abs(float(p[0])), abs(float(p[1]))) for p in regiao)
        if max_val <= 1.0:
            return [[float(ponto[0]), float(ponto[1])] for ponto in regiao]

        return [
            [round(float(ponto[0]) / img_largura, 4), round(float(ponto[1]) / img_altura, 4)]
            for ponto in regiao
        ]

    def caixas_intersectam(self, caixa1: tuple, caixa2: tuple) -> bool:
        """Verifica sobreposição entre duas caixas (x1, y1, x2, y2)."""
        x11, y11, x12, y12 = caixa1
        x21, y21, x22, y22 = caixa2

        return not (
            x12 < x21 or
            x11 > x22 or
            y12 < y21 or
            y11 > y22
        )

    def regiao_para_caixa(self, regiao: list[tuple[int, int]]) -> tuple[int, int, int, int]:
        """Converte uma lista de pontos poligonais em uma caixa delimitadora (x_min, y_min, x_max, y_max)."""
        
        if not regiao:
            return 0, 0, 0, 0
        
        xs = [p[0] for p in regiao]
        ys = [p[1] for p in regiao]

        return min(xs), min(ys), max(xs), max(ys)

    def objeto_intersecta_poligono(self, caixa_xyxy: tuple, poligono_pixels: list | np.ndarray) -> bool:
        """
        Verifica se a base/pés da detecção está dentro do contorno do polígono.
        """
        # Proteção contra polígono vazio ou incompleto (mínimo de 3 vértices)
        if poligono_pixels is None or len(poligono_pixels) < 3:
            return False

        # Converte para array com tipo np.int32 ou np.float32 exigido pelo OpenCV
        contorno = np.array(poligono_pixels, dtype=np.int32)

        # Garante que o contorno tenha pelo menos 3 pontos reais após a conversão
        if contorno.shape[0] < 3:
            return False

        # Ponto de contato no chão (centro horizontal e base da bounding box)
        x1, y1, x2, y2 = caixa_xyxy
        pe_x = float((x1 + x2) / 2.0)
        pe_y = float(y2)

        # Executa a checagem
        distancia = cv2.pointPolygonTest(contorno, (pe_x, pe_y), measureDist=False)
        return distancia >= 0

    def epi_pertence_a_pessoa(self, caixa_epi: tuple, caixa_pessoa: tuple) -> float:
        """
            Retorna um score de associação (0.0 a 1.0) entre um EPI e uma pessoa.
            Considera uma margem extra de 10% no topo da pessoa para acomodar capacetes.
        """
        ex1, ey1, ex2, ey2 = caixa_epi
        px1, py1, px2, py2 = caixa_pessoa

        altura_pessoa = max(1.0, py2 - py1)
        largura_pessoa = max(1.0, px2 - px1)

        # Expande levemente o topo (capacete) e as laterais (luvas)
        py1_exp = py1 - int(0.12 * altura_pessoa)
        px1_exp = px1 - int(0.08 * largura_pessoa)
        px2_exp = px2 + int(0.08 * largura_pessoa)

        # Calcula a interseção entre a caixa do EPI e a caixa expandida da pessoa
        inter_x1 = max(ex1, px1_exp)
        inter_y1 = max(ey1, py1_exp)
        inter_x2 = min(ex2, px2_exp)
        inter_y2 = min(ey2, py2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0  # Sem interseção

        area_intersecao = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_epi = max(1.0, (ex2 - ex1) * (ey2 - ey1))

        return area_intersecao / area_epi
