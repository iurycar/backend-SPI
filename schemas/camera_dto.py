from dataclasses import dataclass

@dataclass
class CameraDTO:
    ip: str
    id_setor: int

    @classmethod
    def from_dict(cls, data: dict) -> 'CameraDTO':

        if not isinstance(data, dict):
            raise ValueError("Input data must be a dictionary.")

        ip = data.get('ip')
        id_setor = data.get('id_setor')

        if ip is None or not isinstance(ip, str):
            if len(ip) > 15 or len(ip) == 0:
                raise ValueError("Invalid 'ip' field. It must be a string with a maximum length of 15 characters.")

            raise ValueError("Invalid or missing 'ip' field. It must be a string.")

        if id_setor is None or not isinstance(id_setor, int):
            raise ValueError("Invalid or missing 'id_setor' field. It must be an integer.")

        return cls(
            ip=ip,
            id_setor=id_setor
        )