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

    def _caixas_intersectam(self, caixa1: tuple, caixa2: tuple) -> bool:
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