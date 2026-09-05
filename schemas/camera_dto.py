from dataclasses import dataclass

@dataclass
class CameraDTO:
    ip: str
    id_setor: int
    nome: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> 'CameraDTO':

        if not isinstance(data, dict):
            raise ValueError("Input data must be a dictionary.")

        ip = data.get('ip')
        id_setor = data.get('id_setor')
        nome = data.get('nome')

        if ip is None or not isinstance(ip, str) or len(ip) == 0 or len(ip) > 255:
            raise ValueError("Invalid or missing 'ip' field. It must be a non-empty string with maximum length of 255 characters.")

        if id_setor is None or not isinstance(id_setor, int):
            raise ValueError("Invalid or missing 'id_setor' field. It must be an integer.")

        if nome is not None and not isinstance(nome, str):
            raise ValueError("Invalid 'nome' field. It must be a string or None.")

        return cls(
            ip=ip,
            id_setor=id_setor,
            nome=nome
        )