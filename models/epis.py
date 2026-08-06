
class EPI:
    def __init__(self, id: int, 
                 nome: str,
                 categoria: str,
                 certificado: str,
                 validade: str,
                 estoque: int):
        self.id = id
        self.nome = nome
        self.categoria = categoria
        self.certificado = certificado
        self.validade = validade
        self.estoque = estoque