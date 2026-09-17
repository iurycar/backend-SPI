from dataclasses import dataclass

@dataclass
class CameraDTO:
    ip: str
    id_setor: int
    nome: str = ""
    rotacao: int = 0
    espelhar_horizontal: bool = False
    espelhar_vertical: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> 'CameraDTO':

        if not isinstance(data, dict):
            raise ValueError("Input data must be a dictionary.")

        ip = data.get('ip')
        id_setor = data.get('id_setor')
        nome = data.get('nome', "Sem nome definido")
        rotacao = data.get('rotacao', 0)
        espelhar_horizontal = data.get('espelhar_horizontal', False)
        espelhar_vertical = data.get('espelhar_vertical', False)

        if ip is None or not isinstance(ip, str) or len(ip) == 0 or len(ip) > 255:
            raise ValueError("Invalid or missing 'ip' field. It must be a non-empty string with maximum length of 255 characters.")

        if id_setor is None or not isinstance(id_setor, int):
            raise ValueError("Invalid or missing 'id_setor' field. It must be an integer.")

        if nome is None or not isinstance(nome, str):
            raise ValueError("Invalid 'nome' field. It must be a string or None.")

        if rotacao is None or not isinstance(rotacao, int):
            raise ValueError("Invalid 'rotacao' field. It must be an integer.")

        if rotacao is None or rotacao not in [0, 90, 180, 270]:
            raise ValueError("Invalid 'rotacao' field. It must be one of the following values: 0, 90, 180, 270.")

        if espelhar_horizontal is None or not isinstance(espelhar_horizontal, bool):
            raise ValueError("Invalid 'espelhar_horizontal' field. It must be a boolean.")

        if espelhar_vertical is None or not isinstance(espelhar_vertical, bool):
            raise ValueError("Invalid 'espelhar_vertical' field. It must be a boolean.")

        return cls(
            ip=ip,
            id_setor=id_setor,
            nome=nome,
            rotacao=rotacao,
            espelhar_horizontal=espelhar_horizontal,
            espelhar_vertical=espelhar_vertical
        )