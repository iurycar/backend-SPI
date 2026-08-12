from flask import Blueprint, Response, jsonify
from services.visao_service import generate_frames, get_last_results

visao_bp = Blueprint('visao', __name__)

@visao_bp.route('/video')
def video():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@visao_bp.route('/detections')
def detections():
    return jsonify(get_last_results())