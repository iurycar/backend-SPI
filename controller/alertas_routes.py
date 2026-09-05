from services.alertas_service import AlertasService
from flask import Blueprint, jsonify, request

def create_alertas_bp(connection):
    alertas_bp = Blueprint('alertas', __name__)
    alertas_service = AlertasService(connection)

    @alertas_bp.route('/alertas', methods=['GET'])
    def listar_alertas():
        alertas = alertas_service.obter_alertas()

        if alertas:
            return jsonify(alertas), 200
        else:
            return jsonify({'message': 'Nenhum alerta encontrado'}), 404

    @alertas_bp.route('/alertas/camera/<int:camera_id>', methods=['GET'])
    def listar_alertas_por_camera(camera_id):
        alertas = alertas_service.obter_alertas_por_id_camera(camera_id)

        if alertas:
            return jsonify(alertas), 200
        else:
            return jsonify({'message': 'Nenhum alerta encontrado para a câmera especificada'}), 404

    @alertas_bp.route('/alertas/zona/<int:zona_id>', methods=['GET'])
    def listar_alertas_por_zona(zona_id):
        alertas = alertas_service.obter_alertas_por_id_zona(zona_id)

        if alertas:
            return jsonify(alertas), 200
        else:
            return jsonify({'message': 'Nenhum alerta encontrado para a zona especificada'}), 404

    @alertas_bp.route('/alertas/<int:alerta_id>', methods=['GET'])
    def obter_alerta_por_id(alerta_id):
        alerta = alertas_service.obter_alerta_por_id(alerta_id)

        if alerta:
            return jsonify(alerta), 200
        else:
            return jsonify({'message': 'Alerta não encontrado'}), 404

    @alertas_bp.route('/alertas/<int:alerta_id>/resolvido', methods=['PUT'])
    def marcar_alerta_resolvido(alerta_id):
        sucesso = alertas_service.marcar_alerta_resolvido(alerta_id)

        if sucesso:
            return jsonify({'message': 'Alerta marcado como resolvido'}), 200
        else:
            return jsonify({'message': 'Falha ao marcar alerta como resolvido'}), 400

    @alertas_bp.route('/alertas/<int:alerta_id>', methods=['DELETE'])
    def deletar_alerta(alerta_id):
        sucesso = alertas_service.deletar_alerta(alerta_id)

        if sucesso:
            return jsonify({'message': 'Alerta deletado com sucesso'}), 200
        else:
            return jsonify({'message': 'Falha ao deletar alerta'}), 400

    @alertas_bp.route('/alertas/estatisticas/epi', methods=['GET'])
    def estatisticas_alertas_por_epi():
        estatisticas = alertas_service.obter_contagem_por_tipo_epi()

        return jsonify(estatisticas), 200

    @alertas_bp.route('/alertas/estatisticas/periodo', methods=['GET'])
    def estatisticas_alertas_por_periodo():
        periodo = request.args.get('periodo', default=30, type=str)

        estatisticas = alertas_service.obter_contagem_por_periodo(periodo)

        return jsonify(estatisticas), 200

    return alertas_bp