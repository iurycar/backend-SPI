import math

"""
    Mixin para avaliação biomecânica, inclinação, rotação e detecção de quedas com YOLO Pose.
"""

class VisaoPosturaMixin:
    LIMIAR_CONF_KEYPOINT = 0.5  # Confiança mínima para considerar o ponto visível

    def _calcular_angulo_articulacao(self, a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        """Calcula o ângulo interno (em graus) no vértice 'b' formado pelos pontos a-b-c."""
        ang_ba = math.atan2(a[1] - b[1], a[0] - b[0]) # ângulo entre b e a
        ang_bc = math.atan2(c[1] - b[1], c[0] - b[0]) # ângulo entre b e c
        angulo = abs(math.degrees(ang_ba - ang_bc)) # diferença absoluta entre os ângulos

        return 360.0 - angulo if angulo > 180.0 else angulo

    def _verificar_agachamento_geometrico(
        self,
        pt_ombro: tuple[float, float],
        pt_quadril: tuple[float, float],
        quadril_esq: tuple[float, float],
        quadril_dir: tuple[float, float],
        joelho_esq: tuple[float, float],
        joelho_dir: tuple[float, float],
        tornozelo_esq: tuple[float, float],
        tornozelo_dir: tuple[float, float],
    ) -> bool:
        """
            Detecta agachamento tanto de perfil quanto de frente:
            1. De perfil: ângulo do joelho flexionado (< 135°).
            2. De frente: queda vertical do quadril em direção aos joelhos (dy_coxa reduzido ou negativo).
        """
        joelhos_validos = [joelho for joelho in [joelho_esq, joelho_dir] if joelho is not None]
        if not joelhos_validos:
            return False  # Sem joelhos visíveis, não é possível avaliar agachamento

        altura_tronco = max(math.dist(pt_ombro, pt_quadril), 1.0)
        media_y_joelhos = sum(joelho[1] for joelho in joelhos_validos) / len(joelhos_validos)
        
        dy_coxa = media_y_joelhos - pt_quadril[1]
        razao_coxa_tronco = dy_coxa / altura_tronco

        # 1 - Avaliação do ângulo do joelho, quando tornozelo e joelho estão visíveis
        angulos_joelho = []
        if quadril_esq and joelho_esq and tornozelo_esq:
            angulos_joelho.append(self._calcular_angulo_articulacao(quadril_esq, joelho_esq, tornozelo_esq))

        if quadril_dir and joelho_dir and tornozelo_dir:
            angulos_joelho.append(self._calcular_angulo_articulacao(quadril_dir, joelho_dir, tornozelo_dir))
        
        # Se há ângulo de joelho visível: joelho dobrado (< 135°) + quadril baixo    
        if angulos_joelho and min(angulos_joelho) < 135.0 and razao_coxa_tronco < 0.85:
            return True

        # 2 - Avaliação de frente (onde o ângulo 2D do joelho sofre projeção e parece ~180°)
        # Em agachamento, o quadril desce até a altura dos joelhos
        if dy_coxa < (altura_tronco * 0.45):
            return True

        # 3 - Comparação com a canela quando tornozelos são visíveis 
        tornozelos_validos = [tornozelo for tornozelo in (tornozelo_esq, tornozelo_dir) if tornozelo is not None]
        if tornozelos_validos:
            media_y_tornozelos = sum(t[1] for t in tornozelos_validos) / len(tornozelos_validos)
            dy_canela = max(media_y_tornozelos - media_y_joelhos, 1.0)

            # Coxa muito menor que a canela indica joelho flexionado em direção à câmera
            if (dy_coxa / dy_canela) < 0.55:
                return True

        return False

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
            LIMITE_RAZAO_FRONTAL = 1.15

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

            pt_ombro = ((ombro_esq[0] + ombro_dir[0]) / 2, (ombro_esq[1] + ombro_dir[1]) / 2)
            pt_quadril = ((quadril_esq[0] + quadril_dir[0]) / 2, (quadril_esq[1] + quadril_dir[1]) / 2)

            pontos_corpo = [
                ponto for ponto in [ombro_esq, ombro_dir, quadril_esq, quadril_dir, joelho_esq, joelho_dir, tornozelo_esq, tornozelo_dir]
                if ponto is not None
            ]
            
            min_x = min(ponto[0] for ponto in pontos_corpo)
            max_x = max(ponto[0] for ponto in pontos_corpo)
            min_y = min(ponto[1] for ponto in pontos_corpo)
            max_y = max(ponto[1] for ponto in pontos_corpo)

            largura_total = max_x - min_x
            altura_total = max(max_y - min_y, 1)
            proporcao = largura_total / altura_total

            largura_ombros = max(math.dist(ombro_esq, ombro_dir), 1.0)
            altura_tronco = math.dist(pt_ombro, pt_quadril)

            dx_coluna = abs(pt_ombro[0] - pt_quadril[0])
            dy_coluna = abs(pt_quadril[1] - pt_ombro[1])
            angulo_horizontal_coluna = math.degrees(math.atan2(dy_coluna, max(dx_coluna, 1)))

            joelhos_validos = [joelho for joelho in (joelho_esq, joelho_dir) if joelho is not None]
            tornozelos_validos = [tornozelo for tornozelo in (tornozelo_esq, tornozelo_dir) if tornozelo is not None]

            media_y_joelhos = (sum(joelho[1] for joelho in joelhos_validos) / len(joelhos_validos)) if joelhos_validos else pt_quadril[1]
            media_y_tornozelos = (sum(tornozelo[1] for tornozelo in tornozelos_validos) / len(tornozelos_validos)) if tornozelos_validos else media_y_joelhos

            dy_pernas = media_y_tornozelos - pt_quadril[1]
            dy_canela = media_y_tornozelos - media_y_joelhos
            dy_tronco = pt_quadril[1] - pt_ombro[1]
            razao_altura_corpo = altura_total / largura_ombros
            razao_tronco = altura_tronco / largura_ombros

            # Identifica se as pernas estão de fato sustentando o corpo em pé (ambas as partes da perna estendidas)
            pernas_verticais_em_pe = (
                tornozelos_validos and
                dy_pernas > (largura_ombros * 1.6) and
                dy_canela > (largura_ombros * 0.7)
            )

            is_agachado = False
            if dy_tronco > (largura_ombros * 0.4):
                is_agachado = self._verificar_agachamento_geometrico(
                    pt_ombro, pt_quadril, quadril_esq, quadril_dir, joelho_esq, joelho_dir, tornozelo_esq, tornozelo_dir
                )

            # Queda horizontal (atravessada/de lado na câmera)
            queda_horizontal = (proporcao > 1.20 and angulo_horizontal_coluna <= 35.0)

            # Queda invertida: ombros no chão abaixo do quadril
            queda_vertical_invertida = (
                not pernas_verticais_em_pe and 
                (
                    pt_ombro[1] >= (pt_quadril[1] - largura_ombros * 0.35) or  # Ombros abaixo ou no mesmo nível
                    (dy_tronco < (largura_ombros * 0.45) and razao_altura_corpo < 2.5)  # Forte compressão de cabeça para a frente
                )
            )

            # Queda com os pés voltados para a câmera (longitudinal com escorço no chão)
            pes_a_frente = (
                pt_ombro[1] < pt_quadril[1] and
                (media_y_tornozelos > pt_quadril[1] or media_y_joelhos > pt_quadril[1])
            )

            # Em pé inclinando para frente: pernas verticais e tronco dobrado (dy_tronco quase nulo ou altura alta)
            em_pe_inclinando_frente = (
                pernas_verticais_em_pe and
                (dy_tronco < (altura_total * 0.22) or razao_altura_corpo < 2.9)
            )

            queda_pes_para_frente = (
                pes_a_frente and
                razao_altura_corpo < 2.9 and
                razao_tronco < 1.35 and
                dy_tronco >= (altura_total * 0.18) and
                not em_pe_inclinando_frente and
                not is_agachado
            )

            if queda_horizontal or queda_vertical_invertida or queda_pes_para_frente:
                is_ma_postura = True
                motivo = "Pessoa caída no chão."
                
            centro_x = int((min_x + max_x) / 2)
            centro_y = int((min_y + max_y) / 2)
            return is_ma_postura, motivo, (centro_x, centro_y), (centro_x, centro_y)

        elif metodo == "agachado":
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

            pt_ombro = ((ombro_esq[0] + ombro_dir[0]) / 2, (ombro_esq[1] + ombro_dir[1]) / 2)
            pt_quadril = ((quadril_esq[0] + quadril_dir[0]) / 2, (quadril_esq[1] + quadril_dir[1]) / 2)

            if self._verificar_agachamento_geometrico(
                pt_ombro, pt_quadril, quadril_esq, quadril_dir, joelho_esq, joelho_dir, tornozelo_esq, tornozelo_dir
            ):
                is_ma_postura = True
                motivo = "Pessoa agachada."

            return is_ma_postura, motivo, (0, 0), (0, 0)

        return False, "", (0, 0), (0, 0)

    def _ponto_valido(self, ponto: tuple[float, float], conf: float) -> bool:
        """Verifica se o ponto possui coordenadas reais e confiança mínima aceitável."""
        return ponto[0] > 0 and ponto[1] > 0 and conf >= self.LIMIAR_CONF_KEYPOINT

    def _obter_ponto_filtrado(self, pontos: list[tuple[float, float]], confs: list[float], indice: int) -> tuple[float, float] | None:
        """Retorna a tupla (x, y) apenas se o keypoint atingir a confiança mínima; caso contrário, retorna None."""
        ponto = pontos[indice]
        conf = confs[indice] if confs is not None and indice < len(confs) else 1.0
        return (float(ponto[0]), float(ponto[1])) if self._ponto_valido(ponto, conf) else None

    def validar_e_avaliar_postura(
        self, camera_id: int, track_id: int, pontos, confs, em_zona: bool = False
    ):
        """Avalia a postura apenas se as articulações necessárias estiverem visíveis."""

        ombro_esq = self._obter_ponto_filtrado(pontos, confs, 5)
        ombro_dir = self._obter_ponto_filtrado(pontos, confs, 6)
        quadril_esq = self._obter_ponto_filtrado(pontos, confs, 11)
        quadril_dir = self._obter_ponto_filtrado(pontos, confs, 12)

        if any(ponto is None for ponto in [ombro_esq, ombro_dir, quadril_esq, quadril_dir]):
            return False, "Articulações oclusas ou fora do campo de visão", None, None, "cinza"

        joelho_esq = self._obter_ponto_filtrado(pontos, confs, 13)
        joelho_dir = self._obter_ponto_filtrado(pontos, confs, 14)
        tornozelo_esq = self._obter_ponto_filtrado(pontos, confs, 15)
        tornozelo_dir = self._obter_ponto_filtrado(pontos, confs, 16)

        # Avaliação de Queda
        queda, motivo_queda, _, _ = self._avaliar_postura(
            "queda",
            ombro_esq=ombro_esq, ombro_dir=ombro_dir,
            quadril_esq=quadril_esq, quadril_dir=quadril_dir,
            joelho_esq=joelho_esq, joelho_dir=joelho_dir,
            tornozelo_esq=tornozelo_esq, tornozelo_dir=tornozelo_dir,
        )

        # Avaliação de Agachamento
        if em_zona and not queda:
            agachado, motivo_agachado, _, _ = self._avaliar_postura(
                "agachado",
                ombro_esq=ombro_esq, ombro_dir=ombro_dir,
                quadril_esq=quadril_esq, quadril_dir=quadril_dir,
                joelho_esq=joelho_esq, joelho_dir=joelho_dir,
                tornozelo_esq=tornozelo_esq, tornozelo_dir=tornozelo_dir,
            )
        else:
            agachado, motivo_agachado = False, ""
        
        ma_postura, motivo_tronco = False, ""
        ma_rot, motivo_rot = False, ""
        pt_ombro, pt_quadril = None, None

        if not queda and not agachado:
            # Avaliação do Tronco
            ma_postura, motivo_tronco, pt_ombro, pt_quadril = self._avaliar_postura(
                "tronco",
                ombro_esq=ombro_esq, ombro_dir=ombro_dir,
                quadril_esq=quadril_esq, quadril_dir=quadril_dir,
            )

            # Avaliação de Rotação
            ma_rot, motivo_rot, _, _ = self._avaliar_postura(
                "rotacao",
                ombro_esq=ombro_esq, ombro_dir=ombro_dir,
                quadril_esq=quadril_esq, quadril_dir=quadril_dir,
            )
        else:
            pt_ombro = ((ombro_esq[0] + ombro_dir[0]) / 2, (ombro_esq[1] + ombro_dir[1]) / 2)
            pt_quadril = ((quadril_esq[0] + quadril_dir[0]) / 2, (quadril_esq[1] + quadril_dir[1]) / 2)

        self._monitorar_tempo_postura(
            camera_id=camera_id, track_id=track_id, tipo_deteccao="queda",
            motivo=motivo_queda if queda else "Em pé",
            ativo=queda, tempo_limite_segundos=3, severidade=3,
        )

        self._monitorar_tempo_postura(
            camera_id=camera_id, track_id=track_id, tipo_deteccao="agachado",
            motivo=motivo_agachado if agachado else "Em pé",
            ativo=agachado, tempo_limite_segundos=3, severidade=1,
        )

        self._monitorar_tempo_postura(
            camera_id=camera_id, track_id=track_id, tipo_deteccao="postura_tronco",
            motivo=motivo_tronco if ma_postura else "Postura normal",
            ativo=ma_postura, tempo_limite_segundos=10, severidade=1,
        )

        self._monitorar_tempo_postura(
            camera_id=camera_id, track_id=track_id, tipo_deteccao="postura_rotacao",
            motivo=motivo_rot if ma_rot else "Sem rotacao excessiva",
            ativo=ma_rot, tempo_limite_segundos=10, severidade=1,
        )

        if queda:
            is_ma_postura = True
            motivo = motivo_queda
            cor_esqueleto = "vermelho"
        elif agachado:
            is_ma_postura = True
            motivo = motivo_agachado
            cor_esqueleto = "laranja"
        elif ma_postura:
            is_ma_postura = True
            cor_esqueleto = "amarelo"
            motivo = motivo_tronco
        elif ma_rot:
            is_ma_postura = True
            cor_esqueleto = "amarelo"
            motivo = motivo_rot
        else:
            is_ma_postura = False
            motivo = "Postura normal"
            cor_esqueleto = "ciano"

        #cor_esqueleto = "vermelho" if (queda or agachado or ma_rot or ma_postura) else "ciano"

        return is_ma_postura, motivo, pt_ombro, pt_quadril, cor_esqueleto