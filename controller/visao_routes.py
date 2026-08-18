from services.visao_service import generate_frames, get_last_results
from flask import Blueprint, Response, jsonify

visao_bp = Blueprint('visao', __name__)

def create_visao_bp(connection):
    @visao_bp.route('/video', defaults={'camera_id': 1}, methods=['GET'])
    @visao_bp.route('/video/', defaults={'camera_id': 1}, methods=['GET'])
    @visao_bp.route('/video/<int:camera_id>', methods=['GET'])
    def video(camera_id=1): 
        return Response(
            generate_frames(connection, camera_id),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    @visao_bp.route('/detections', methods=['GET'])
    def detections():
        return jsonify(get_last_results())

    return visao_bp