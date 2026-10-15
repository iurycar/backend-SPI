from collections import defaultdict, deque
from contextlib import contextmanager
import threading
import time
import os

"""
    Módulo de perfilamento leve por etapas (Stage Profiler) para o pipeline de visão.

    Permite medir com precisão em milissegundos o tempo gasto em cada etapa do processamento
    (captura, pré-processamento, inferência YOLO, rastreamento ByteTrack, pós-processamento, desenho e codificação JPEG).
"""

PROFILING_ATIVO = os.getenv("VISION_PROFILE", "1") != "0"
INTERVALO_RELATORIO = float(os.getenv("VISION_PROFILE_EVERY", "5"))

def _calcular_percentil0(valores_ordenados: list[float], percentil: float) -> float:
    """Calcula o percentil de uma lista de valores ordenados."""
    if not valores_ordenados:
        return 0.0

    indice = int(round(percentil * (len(valores_ordenados) - 1)))
    
    return valores_ordenados[indice]



def _calcular_fps(timestamps: list[float]) -> float:
    """Calcula a taxa de quadros por segundo (FPS) com base no histórico de timestamps."""
    if len(timestamps) < 2:
        return 0.0
    
    tempo_total = timestamps[-1] - timestamps[0]
    return (len(timestamps) - 1) / tempo_total if tempo_total > 0 else 0.0


class StageProfiler:
    """
        Monitora e calcula estatísticas de desempenho para diferentes etapas do pipeline de visão.
    """
    def __init__(
            self, 
            nome: str = "visao", 
            janela_amostras: int = 240,
            intervalo_relatorio: float = INTERVALO_RELATORIO, 
            habilitado: bool = PROFILING_ATIVO,
            saida_log=print
        ):
        
        self.nome = nome
        self.habilitado = habilitado
        self.intervalo_relatorio = intervalo_relatorio
        self.saida_log = saida_log

        # Estruturas de dados para armazenar tempos e ticks
        self._lock = threading.Lock()
        self._tempos_ms: dict[str, deque] = defaultdict(lambda: deque(maxlen=janela_amostras))
        self._marcas_tempo: dict[str, deque] = defaultdict(lambda: deque(maxlen=janela_amostras))
        self._proximo_relatorio = time.monotonic() + intervalo_relatorio

    @contextmanager
    def etapa(self, nome_etapa: str):
        """
        Gerenciador de contexto para medir o tempo de execução de um bloco de código.
        Uso:
            with profiler.etapa("inferencia.epi"):
                modelo.predict(...)
        """
        
        if not self.habilitado:
            yield
            return
        
        inicio = time.perf_counter()
        try:
            yield
        
        finally:
            duracao_ms = (time.perf_counter() - inicio) * 1000
            self.adicionar_tempo(nome_etapa, duracao_ms)

    def adicionar_tempo(self, nome_etapa: str, duracao_ms: float) -> None:
        """Registra manualmente o tempo de execução em milissegundos de uma etapa."""
        if not self.habilitado:
            return
        
        with self._lock:
            self._tempos_ms[nome_etapa].append(float(duracao_ms))

    def marcar_evento(self, identificador_fps: str) -> None:
        """Registra a ocorrência de um evento para o cálculo contínuo de FPS."""
        if not self.habilitado:
            return
        
        with self._lock:
            self._marcas_tempo[identificador_fps].append(time.monotonic())

    
    def obter_estatisticas(self) -> dict:
        """Retorna um snapshot das estatísticas atuais de desempenho."""
        with self._lock:
            copia_tempos = {key: list(value) for key, value in self._tempos_ms.items()}
            copia_marcas = {key: list(value) for key, value in self._marcas_tempo.items()}

        estatisticas_etapas = {}
        for etapa_nome, valores in copia_tempos.items():
            if not valores:
                continue

            valores_ord = sorted(valores)
            estatisticas_etapas[etapa_nome] = {
                "amostras": len(valores_ord),
                "media": sum(valores_ord) / len(valores_ord),
                "p50": _calcular_percentil0(valores_ord, 0.5),
                "p95": _calcular_percentil0(valores_ord, 0.95),
                "max": valores_ord[-1]
            }

        estatisticas_fps = {key: _calcular_fps(values) for key, values in copia_marcas.items()}

        return {
            "etapas": estatisticas_etapas,
            "fps": estatisticas_fps
        }
    
    def emitir_relatorio(self, forcar: bool = False) -> None:
        """Emite o relatório de métricas noconsole se o intervalo tiver expirado."""
        
        if not self.habilitado:
            return
        
        agora = time.monotonic()
        if not forcar and agora < self._proximo_relatorio:
            return
        
        self._proximo_relatorio = agora + self.intervalo_relatorio

        dados = self.obter_estatisticas()
        etapas, fps = dados["etapas"], dados["fps"]
        
        if not etapas and not fps:
            return

        # Identifica a etapa individual que mais consome tempo (gargalo do pipeline)
        etapas_individuais = {key: value for key, value in etapas.items()
                       if not key.startswith(("total.", "e2e."))}
        
        gargalo = max(etapas_individuais, key=lambda k: etapas_individuais[k]["media"], default=None)

        linhas = [
            f"[PERF:{self.nome.upper()}] {'Etapa':<28}{'Amostras':>6}{'Média':>9}{'P50':>9}{'P95':>9}{'Máx':>9}  (ms)"
        ]
        
        for nome_etapa in sorted(etapas):
            dados_etapa = etapas[nome_etapa]
            identificador_gargalo = "  <-- gargalo" if nome_etapa == gargalo else ""
            linhas.append(
                f"[PERF:{self.nome.upper()}] {nome_etapa:<28}"
                f"{dados_etapa['amostras']:>6}"
                f"{dados_etapa['media']:>9.1f}"
                f"{dados_etapa['p50']:>9.1f}"
                f"{dados_etapa['p95']:>9.1f}"
                f"{dados_etapa['max']:>9.1f}"
                f"{identificador_gargalo}"
            )

        for nome_fps in sorted(fps):
            linhas.append(f"[PERF:{self.nome.upper()}] {nome_fps:<28}{fps[nome_fps]:>6.1f} fps")
        
        self.saida_log("\n".join(linhas))