from flask import Blueprint, Response, jsonify, request
from services.visao_service import VisaoService
from worker.vision_manager import workers
import time
import os

visao_bp = Blueprint('visao', __name__)


def create_visao_bp(connection):
    visao_service = VisaoService(connection)

    @visao_bp.route('/video', defaults={'camera_id': 1}, methods=['GET'])
    @visao_bp.route('/video/', defaults={'camera_id': 1}, methods=['GET'])
    @visao_bp.route('/video/<int:camera_id>', methods=['GET'])
    def video(camera_id=1):
        worker = workers.get(camera_id)

        if not worker:
            return jsonify({"message": f"Worker para a câmera {camera_id} não está em execução."}), 503

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

    @visao_bp.route('/detections/<int:camera_id>', methods=['GET'])
    def detections(camera_id):
        if workers:
            worker = workers.get(camera_id)

            if worker is None:
                return jsonify({"message": f"Worker para a câmera {camera_id} não está em execução."}), 503

            dados = {
                "detections": worker.last_results.get('detections', []),
                "class_count": worker.last_results.get('class_count', {}),
                "connected": worker.last_results.get('connected', False),
            }

            return jsonify(dados), 200
        
        return jsonify({"detections": [], "zonas": []}), 200

    @visao_bp.route('/active-learning/toggle', methods=['POST'])
    def toggle_active_learning():
        """
        Ativa ou desativa a captura de Active Learning.
        Corpo da requisição (JSON): {"enabled": true} ou {"enabled": false}
        """
        dados = request.json or {}
        enabled = dados.get('enabled', True)
        
        # Caminho compartilhado para a flag
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))
        flag_path = os.path.join(BASE_DIR, 'assets', 'modelo', 'active_learning', 'active_learning.flag')
        
        if enabled:
            # Cria o arquivo para ativar
            with open(flag_path, 'w') as f:
                f.write('1')
            msg = "Active Learning ativado com sucesso."
        else:
            # Apaga o arquivo para desativar
            with open(flag_path, 'w') as f:
                f.write('0')
            msg = "Active Learning desativado com sucesso."
                
        return jsonify({"message": msg, "enabled": enabled}), 200

    return visao_bp