"""Tipos persistidos e filtros de alertas, independentes do texto do evento."""

TIPOS_POSTURA = ('postura_tronco', 'postura_rotacao', 'queda')
TIPOS_CRIACAO = ('epi', *TIPOS_POSTURA)
TIPOS_FILTRO = (*TIPOS_CRIACAO, 'legado', 'postura')


def tipos_do_filtro(tipo: str | None) -> tuple[str, ...] | None:
    if tipo is None:
        return None
    if tipo not in TIPOS_FILTRO:
        raise ValueError('tipo inválido; informe um dos valores permitidos.')
    return TIPOS_POSTURA if tipo == 'postura' else (tipo,)


def validar_vinculo_alerta(tipo: str, id_monitorar: int | None,
                          id_camera: int | None) -> None:
    if tipo not in TIPOS_CRIACAO:
        raise ValueError('tipo_deteccao inválido para criação de alerta.')
    if tipo == 'epi':
        if type(id_monitorar) is not int or id_monitorar <= 0 or id_camera is not None:
            raise ValueError('EPI exige monitoramento e não aceita câmera direta.')
    elif type(id_camera) is not int or id_camera <= 0 or id_monitorar is not None:
        raise ValueError('Postura exige câmera direta e não aceita monitoramento.')
