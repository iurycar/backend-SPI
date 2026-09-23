from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class IntervaloDTO:
    data_inicio: str
    data_fim: str

    @classmethod
    def from_query_args(cls, args):
        agora = datetime.now()

        # Se não passar parâmetros, padrão = últimos 30 dias
        inicio_padrao = (agora - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
        fim_padrao = agora.strftime('%Y-%m-%d 23:59:59')

        inicio = args.get('data_inicio', inicio_padrao)
        fim = args.get('data_fim', fim_padrao)

        return cls(
            data_inicio=inicio,
            data_fim=fim
        )