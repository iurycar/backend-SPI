from services.alertas_service import AlertasService
from flask import Blueprint, jsonify, request
from core.tipo_deteccao import tipos_do_filtro

def create_alertas_bp(connection):
    alertas_bp = Blueprint('alertas', __name__)
    alertas_service = AlertasService(connection)

    def obter_tipo():
        valores = request.args.getlist('tipo')
        if len(valores) > 1:
            raise ValueError('tipo inválido; informe um dos valores permitidos.')
        tipo = valores[0] if valores else None
        tipos_do_filtro(tipo)
        return tipo

    @alertas_bp.route('/alertas', methods=['GET'])
    def listar_alertas():
        try:
            tipo = obter_tipo()
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        alertas = alertas_service.obter_alertas(tipo)

        if alertas:
            return jsonify(alertas), 200
        else:
            return jsonify({'message': 'Nenhum alerta encontrado'}), 404

    @alertas_bp.route('/alertas/camera/<int:camera_id>', methods=['GET'])
    def listar_alertas_por_camera(camera_id):
        try:
            tipo = obter_tipo()
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        alertas = alertas_service.obter_alertas_por_id_camera(camera_id, tipo)

        if alertas:
            return jsonify(alertas), 200
        else:
            return jsonify({'message': 'Nenhum alerta encontrado para a câmera especificada'}), 404

    @alertas_bp.route('/alertas/zona/<int:zona_id>', methods=['GET'])
    def listar_alertas_por_zona(zona_id):
        try:
            tipo = obter_tipo()
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        alertas = alertas_service.obter_alertas_por_id_zona(zona_id, tipo)

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
        try:
            periodo = int(request.args.get('periodo', '30'))
            if periodo < 1:
                raise ValueError
        except ValueError:
            return jsonify({'message': 'periodo deve ser um número inteiro positivo de dias.'}), 400

        try:
            estatisticas = alertas_service.obter_contagem_por_periodo(periodo)
        except OverflowError:
            return jsonify({'message': 'periodo excede o intervalo de datas suportado.'}), 400

        return jsonify(estatisticas), 200

    return alertas_bp
