from dataclasses import dataclass

@dataclass
class EpiDTO:
    nome: str
    categoria: str
    certificado: str
    validade: str
    estoque: int
    quantidade_min: int
    em_uso: int

    @classmethod
    def from_dict(cls, data: dict):

        if not isinstance(data, dict):
            raise ValueError("Payload invalid.")

        nome = data.get('nome')
        categoria = data.get('categoria')
        certificado = data.get('certificado')
        validade = data.get('validade')
        estoque = data.get('estoque')
        quantidade_min = data.get('quantidade_min')
        em_uso = data.get('em_uso')

        if not isinstance(nome, str):
            raise ValueError("Nome must be a string.")

        if not isinstance(categoria, str):
            raise ValueError("Categoria must be a string.")

        if not isinstance(certificado, str):
            raise ValueError("Certificado must be a string.")

        if not isinstance(validade, str):
            raise ValueError("Validade must be a string.")

        if not isinstance(estoque, int):
            raise ValueError("Estoque must be an integer.")

        if not isinstance(quantidade_min, int):
            raise ValueError("Quantidade Min must be an integer.")

        if not isinstance(em_uso, int):
            raise ValueError("Em Uso must be an integer.")

        return cls(
            nome=nome,
            categoria=categoria,
            certificado=certificado,
            validade=validade,
            estoque=estoque,
            quantidade_min=quantidade_min,
            em_uso=em_uso
        )