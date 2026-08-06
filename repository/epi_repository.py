
class EpiRepository:
    def listar_epis(self) -> list[dict]:
        # Simulação de dados de EPIs
        return [
            {"id": 1, "nome": "Capacete", "categoria": "Cabeça", "certificado": "CA 498", "estoque": 10},
            {"id": 2, "nome": "Luvas", "categoria": "Mãos", "certificado": "CA 32041", "estoque": 0},
            {"id": 3, "nome": "Óculos de Proteção", "categoria": "Olhos", "certificado": "CA 10344", "estoque": -5},
            {"id": 4, "nome": "Botinas", "categoria": "Pés", "certificado": "CA 17148", "estoque": 15},
        ]