"""Opt-in observations of the existing cooldown; no deduplication policy change."""
import json
import os
import time


def trace_alert_candidate(kind, camera_id, zone_id, event, track_id, acquired):
    if os.getenv('ALERT_DIAGNOSTICS', 'false').lower() != 'true':
        return
    
    print(json.dumps({
        'diagnostic': 'alert_candidate', 'timestamp': time.time(),
        'kind': kind, 'camera_id': camera_id, 'zone_id': zone_id,
        'event': event, 'track_id': track_id, 'cooldown_acquired': bool(acquired),
    }, ensure_ascii=True), flush=True)
