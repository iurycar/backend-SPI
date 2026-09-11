"""Per-camera processing measurements, independent of HTTP polling."""
from collections import deque

FPS_WINDOW_SECONDS = 3.0
RESULT_TIMEOUT_SECONDS = 5.0


def processing_fps(completions, now):
    recent = [t for t in completions if 0 <= now - t <= FPS_WINDOW_SECONDS]
    if len(recent) < 2:
        return 0.0
    elapsed = now - recent[0]
    return round((len(recent) - 1) / elapsed, 2) if elapsed > 0 else 0.0


class FrameMetrics:
    def __init__(self):
        self.completions = deque()

    def complete(self, captured_at, completed_at):
        self.completions.append(completed_at)
        while self.completions and completed_at - self.completions[0] > FPS_WINDOW_SECONDS:
            self.completions.popleft()
        return {
            'completed_at': completed_at,
            'completions': tuple(self.completions),
            'latencia_ms': round(max(0.0, completed_at - captured_at) * 1000, 2),
        }


def empty_detection_snapshot():
    return {'detections': [], 'class_count': {}, 'connected': False,
            'fps': 0.0, 'latencia_ms': None}


def detection_snapshot(result, connected, now):
    snapshot = empty_detection_snapshot()
    snapshot['connected'] = bool(connected)
    completed_at = result.get('completed_at')
    if not connected or completed_at is None or not 0 <= now - completed_at < RESULT_TIMEOUT_SECONDS:
        return snapshot
    snapshot.update(detections=result.get('detections', []),
                    class_count=result.get('class_count', {}),
                    fps=processing_fps(result.get('completions', ()), now),
                    latencia_ms=result.get('latencia_ms'))
    return snapshot
