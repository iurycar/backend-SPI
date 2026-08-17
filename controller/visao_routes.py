from services.visao_service import generate_frames, get_last_results
from flask import Blueprint, Response, jsonify

visao_bp = Blueprint('visao', __name__)

def create_visao_bp(connection):
    @visao_bp.route('/video')
    def video():
        return Response(generate_frames(connection), mimetype='multipart/x-mixed-replace; boundary=frame')

    @visao_bp.route('/detections')
    def detections():
        return jsonify(get_last_results())

    return visao_bp