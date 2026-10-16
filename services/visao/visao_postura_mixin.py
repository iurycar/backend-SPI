import math

"""
    Mixin para avaliação biomecânica, inclinação, rotação e detecção de quedas com YOLO Pose.
"""

class VisaoPosturaMixin:
    def _avaliar_postura(self, metodo: str, **kargs):
        """
            Avalia a postura combinando ângulo de inclinação do tronco, rotação axial e verificação de queda.
        """

        is_ma_postura = False
        motivo = ""

        if metodo == "tronco":
            ombro_esq = kargs.get("ombro_esq")
            ombro_dir = kargs.get("ombro_dir")
            quadril_esq = kargs.get("quadril_esq")
            quadril_dir = kargs.get("quadril_dir")

            if any(ponto is None for ponto in [ombro_esq, ombro_dir, quadril_esq, quadril_dir]):
                return is_ma_postura, motivo

            pt_ombro = ((ombro_esq[0] + ombro_dir[0]) / 2, (ombro_esq[1] + ombro_dir[1]) / 2)
            pt_quadril = ((quadril_esq[0] + quadril_dir[0]) / 2, (quadril_esq[1] + quadril_dir[1]) / 2)

            dx = pt_ombro[0] - pt_quadril[0]
            dy = pt_quadril[1] - pt_ombro[1]
            
            angulo = math.degrees(math.atan2(abs(dx), abs(dy)))

            largura_ombros = max(math.dist(ombro_esq, ombro_dir), 1)
            altura_tronco = math.dist(pt_ombro, pt_quadril)
            razao_ombro = altura_tronco / largura_ombros

            LIMITE_ANGULO = 30
            LIMITE_RAZAO_FRONTAL = 1.1

            if angulo > LIMITE_ANGULO or razao_ombro < LIMITE_RAZAO_FRONTAL:
                is_ma_postura = True
                motivo = "Inclinação Excessiva do Tronco."

            return is_ma_postura, motivo, (int(pt_ombro[0]), int(pt_ombro[1])), (int(pt_quadril[0]), int(pt_quadril[1]))

        elif metodo == "rotacao":
            ombro_esq = kargs.get("ombro_esq")
            ombro_dir = kargs.get("ombro_dir")
            quadril_esq = kargs.get("quadril_esq")
            quadril_dir = kargs.get("quadril_dir")

            if any(p is None for p in (ombro_esq, ombro_dir, quadril_esq, quadril_dir)):
                return is_ma_postura, motivo, (0, 0), (0, 0)

            dx_ombros = ombro_dir[0] - ombro_esq[0]
            dy_ombros = ombro_dir[1] - ombro_esq[1]
            angulo_ombros = math.degrees(math.atan2(dy_ombros, dx_ombros))

            dx_quadris = quadril_dir[0] - quadril_esq[0]
            dy_quadris = quadril_dir[1] - quadril_esq[1]
            angulo_quadris = math.degrees(math.atan2(dy_quadris, dx_quadris))

            diferenca_rotacao = abs(angulo_ombros - angulo_quadris)
            if diferenca_rotacao > 180:
                diferenca_rotacao = 360 - diferenca_rotacao

            LIMITE_TORCAO = 30
            if diferenca_rotacao > LIMITE_TORCAO:
                is_ma_postura = True
                motivo = "Rotação/Torção Excessiva."

            return is_ma_postura, motivo, (int(ombro_esq[0]), int(ombro_esq[1])), (int(quadril_esq[0]), int(quadril_esq[1]))

        elif metodo == "queda":
            ombro_esq = kargs.get("ombro_esq")
            ombro_dir = kargs.get("ombro_dir")
            quadril_esq = kargs.get("quadril_esq")
            quadril_dir = kargs.get("quadril_dir")
            joelho_esq = kargs.get("joelho_esq")
            joelho_dir = kargs.get("joelho_dir")
            tornozelo_esq = kargs.get("tornozelo_esq")
            tornozelo_dir = kargs.get("tornozelo_dir")

            if any(p is None for p in (ombro_esq, ombro_dir, quadril_esq, quadril_dir)):
                return is_ma_postura, motivo, (0, 0), (0, 0)

            min_x = min(ombro_esq[0], ombro_dir[0], quadril_esq[0], quadril_dir[0])
            max_x = max(ombro_esq[0], ombro_dir[0], quadril_esq[0], quadril_dir[0])
            min_y = min(ombro_esq[1], ombro_dir[1], quadril_esq[1], quadril_dir[1])
            max_y = max(ombro_esq[1], ombro_dir[1], quadril_esq[1], quadril_dir[1])

            largura = max_x - min_x
            altura = max(max_y - min_y, 1)
            proporcao = largura / altura

            pt_ombro = ((ombro_esq[0] + ombro_dir[0]) / 2, (ombro_esq[1] + ombro_dir[1]) / 2)
            pt_quadril = ((quadril_esq[0] + quadril_dir[0]) / 2, (quadril_esq[1] + quadril_dir[1]) / 2)

            dx_coluna = abs(pt_ombro[0] - pt_quadril[0])
            dy_coluna = abs(pt_quadril[1] - pt_ombro[1])
            angulo_horizontal_coluna = math.degrees(math.atan2(dy_coluna, max(dx_coluna, 1)))

            # Filtro para diferenciar pessoa agachada de caída
            is_agachado = False
            pontos_pernas_validos = [
                p[1] for p in [joelho_esq, joelho_dir, tornozelo_esq, tornozelo_dir]
                if p is not None and p[0] > 0 and p[1] > 0
            ]

            if len(pontos_pernas_validos) >= 2:
                media_y_pernas = sum(pontos_pernas_validos) / len(pontos_pernas_validos)
                if pt_quadril[1] < media_y_pernas and angulo_horizontal_coluna > 40.0:
                    is_agachado = True

            LIMITE_QUEDA = 1.2
            if proporcao > LIMITE_QUEDA and angulo_horizontal_coluna <= 35.0 and not is_agachado:
                is_ma_postura = True
                motivo = "Pessoa caída no chão."

            centro_x = int((min_x + max_x) / 2)
            centro_y = int((min_y + max_y) / 2)
            return is_ma_postura, motivo, (centro_x, centro_y), (centro_x, centro_y)

        return False, "", (0, 0), (0, 0)