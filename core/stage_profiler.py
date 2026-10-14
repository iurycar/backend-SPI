"""
Profiler leve por etapa para o pipeline de visão.

Uso:
    prof = StageProfiler("vision")

    with prof.stage("det.postprocess"):
        ...                                   # mede o tempo (ms) do bloco

    prof.add("det.inference", 42.3)           # registra um valor já medido
    prof.tick("cam1.infer_fps")               # conta eventos para calcular FPS
    prof.report()                             # imprime a tabela a cada `report_every` s

Convenções de nome:
    "total.*" e "e2e.*"  -> agregados (não entram na escolha do "gargalo")
    demais               -> etapas individuais

Desligar:  VISION_PROFILE=0
"""
import os
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager

ENABLED = os.getenv("VISION_PROFILE", "1") != "0"
REPORT_EVERY = float(os.getenv("VISION_PROFILE_EVERY", "5"))


def _pct(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(round(p * (len(sorted_vals) - 1)))
    return sorted_vals[idx]


def _fps(ts: list[float]) -> float:
    if len(ts) < 2:
        return 0.0
    span = ts[-1] - ts[0]
    return (len(ts) - 1) / span if span > 0 else 0.0


class StageProfiler:
    def __init__(self, name: str = "vision", window: int = 240,
                 report_every: float = REPORT_EVERY, enabled: bool = ENABLED,
                 sink=print):
        self.name = name
        self.enabled = enabled
        self.report_every = report_every
        self.sink = sink
        self._lock = threading.Lock()
        self._ms: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
        self._ticks: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
        self._next_report = time.monotonic() + report_every

    # ------------------------------------------------------------------ coleta
    @contextmanager
    def stage(self, label: str):
        if not self.enabled:
            yield
            return
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.add(label, (time.perf_counter() - t0) * 1000.0)

    def add(self, label: str, ms: float) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._ms[label].append(float(ms))

    def tick(self, label: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._ticks[label].append(time.monotonic())

    # --------------------------------------------------------------- relatório
    def snapshot(self) -> dict:
        """Estatísticas atuais (útil para expor num endpoint /metrics)."""
        with self._lock:
            ms = {k: list(v) for k, v in self._ms.items()}
            ticks = {k: list(v) for k, v in self._ticks.items()}

        stages = {}
        for label, vals in ms.items():
            s = sorted(vals)
            stages[label] = {
                "n": len(s),
                "mean": sum(s) / len(s),
                "p50": _pct(s, 0.50),
                "p95": _pct(s, 0.95),
                "max": s[-1],
            }
        return {"stages": stages, "fps": {k: _fps(v) for k, v in ticks.items()}}

    def report(self, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and now < self._next_report:
            return
        self._next_report = now + self.report_every

        snap = self.snapshot()
        stages, fps = snap["stages"], snap["fps"]
        if not stages and not fps:
            return

        individuais = {k: v for k, v in stages.items()
                       if not k.startswith(("total.", "e2e."))}
        gargalo = max(individuais, key=lambda k: individuais[k]["mean"], default=None)

        linhas = [f"[perf:{self.name}] {'etapa':<28}{'n':>6}{'média':>9}{'p50':>9}{'p95':>9}{'máx':>9}  (ms)"]
        for label in sorted(stages):
            s = stages[label]
            marca = "  <-- gargalo" if label == gargalo else ""
            linhas.append(
                f"[perf:{self.name}] {label:<28}{s['n']:>6}{s['mean']:>9.1f}"
                f"{s['p50']:>9.1f}{s['p95']:>9.1f}{s['max']:>9.1f}{marca}"
            )
        for label in sorted(fps):
            linhas.append(f"[perf:{self.name}] {label:<28}{fps[label]:>6.1f} fps")
        self.sink("\n".join(linhas))