from services.visao_service import VisaoService
from vision_worker import VisionWorker
from flask import Blueprint, Response, jsonify
import time

visao_bp = Blueprint('visao', __name__)


def create_visao_bp(connection):
    visao_service = VisaoService(connection)
    workers = {}

    @visao_bp.route('/video', defaults={'camera_id': 1}, methods=['GET'])
    @visao_bp.route('/video/', defaults={'camera_id': 1}, methods=['GET'])
    @visao_bp.route('/video/<int:camera_id>', methods=['GET'])
    def video(camera_id=1):
        worker = workers.get(camera_id)
        if worker is None:
            worker = VisionWorker(camera_id=camera_id)
            workers[camera_id] = worker
            worker.start()

        def generate():
            while True:
                frame = worker.next_frame()
                if frame is None:
                    time.sleep(0.03)
                    continue

                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                )

        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @visao_bp.route('/detections', methods=['GET'])
    def detections():
        if workers:
            worker = next(reversed(workers.values()))
            return jsonify(worker.get_last_results())
        return jsonify(visao_service.get_last_results())

    return visao_bp