"""Exercise Windows spawn without loading models, connecting cameras or sending alerts."""
import multiprocessing as mp
import unittest
from unittest.mock import patch

from worker.vision_worker import VisionWorker


def _exercise_batch_target(target, results, stop_event):
    # Runs inside the spawned interpreter; only infrastructure is substituted.
    with patch('connection.conn.Connection'), patch('worker.vision_worker.VisaoService') as service:
        def run_batch(**kwargs):
            results[9] = {'cameras': kwargs['cameras']}
            kwargs['stop_event'].set()
        service.return_value.run_batch_video_loop.side_effect = run_batch
        target([9], {}, results, stop_event, {})


class WorkerSpawnTests(unittest.TestCase):
    def test_batch_target_can_cross_spawn_boundary_without_serializing_manager(self):
        worker = VisionWorker(cameras_lote=[9])
        self.addCleanup(worker.manager.shutdown)
        context = mp.get_context('spawn')
        stop_event = context.Event()
        process = context.Process(
            target=_exercise_batch_target,
            args=(worker._run_batch, worker.last_results, stop_event),
        )
        process.start()
        try:
            process.join(timeout=30)
            self.assertFalse(process.is_alive(), 'Spawned worker failed to complete')
            self.assertEqual(process.exitcode, 0)
            self.assertTrue(stop_event.is_set())
            self.assertEqual(worker.last_results[9], {'cameras': [9]})
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            process.close()
