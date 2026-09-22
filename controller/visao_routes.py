from worker.vision_manager import workers, parar_vision_workers, iniciar_vision_workers
from core.vision_metrics import empty_detection_snapshot
from flask import Blueprint, Response, jsonify, request
from core.auth import login_required, perfil_required
import time
import os

visao_bp = Blueprint('visao', __name__)


def create_visao_bp(connection):

    @visao_bp.route('/video', defaults={'camera_id': 1}, methods=['GET'])
    @visao_bp.route('/video/', defaults={'camera_id': 1}, methods=['GET'])
    @visao_bp.route('/video/<int:camera_id>', methods=['GET'])
    @login_required
    def video(camera_id=1):
        worker = workers.get(camera_id)

        if not worker:
            return jsonify({"message": f"Worker para a câmera {camera_id} não está em execução."}), 503

        def generate():
            while True:
                frame = worker.next_frame(camera_id=camera_id)
                if frame is None:
                    time.sleep(0.03)
                    continue

                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                )

        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


    @visao_bp.route('/detections/<int:camera_id>', methods=['GET'])
    @login_required
    def detections(camera_id):
        worker = workers.get(camera_id)
        if worker is None:
            dados = empty_detection_snapshot()
            dados['message'] = f'Worker para a câmera {camera_id} não está em execução.'
            return jsonify(dados), 503
        return jsonify(worker.get_detection_snapshot(camera_id)), 200


    @visao_bp.route('/active-learning/toggle', methods=['POST'])
    @perfil_required('admin', 'supervisor')
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


    @visao_bp.route('/video/lote/<int:tamanho_lote>', methods=['POST'])
    @perfil_required('admin')
    def modificar_tamanho_lote(tamanho_lote):
        """
            Modifica o tamanho do lote de câmeras processadas por cada worker.
            Corpo da requisição (JSON): {"tamanho_lote": 2}
        """
        if tamanho_lote < 1:
            return jsonify({"message": "O tamanho do lote deve ser pelo menos 1."}), 400

        # Desliga todos os workers
        parar_vision_workers()

        # Reinicia os workers com o novo tamanho de lote
        iniciar_vision_workers(tamanho_lote=tamanho_lote)

        return jsonify({"message": f"Tamanho do lote atualizado para {tamanho_lote}."}), 200

    return visao_bp