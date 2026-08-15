from services.zonas_service import ZonasService
from flask import Blueprint, jsonify, request

def create_zonas_bp(connection):
    zonas_service = ZonasService(connection)
    zonas_bp = Blueprint('zonas_bp', __name__)

    @zonas_bp.route('/zonas', methods=['GET'])
    def listar_zonas():
        zonas = zonas_service.listar_zonas()
        return jsonify(zonas), 200

    @zonas_bp.route('/zonas/<int:zona_id>', methods=['GET'])
    def obter_zona_por_id(zona_id):
        zona = zonas_service.obter_zona_por_id(zona_id)

        if zona:
            return jsonify(zona), 200
        else:
            return jsonify({"error": "Zona não encontrada"}), 404

    @zonas_bp.route('/zonas/registrar', methods=['POST'])
    def registrar_zona():
        data = request.get_json()
        zona = zonas_service.registrar_zona(data)

        if zona:
            return jsonify(zona), 201
        else:
            return jsonify({"error": "Falha ao registrar a zona"}), 400

    @zonas_bp.route('/zonas/<int:zona_id>', methods=['PUT'])
    def atualizar_zona(zona_id):
        data = request.get_json()
        zona = zonas_service.atualizar_zona(zona_id, data)

        if zona:
            return jsonify(zona), 200
        else:
            return jsonify({"error": "Falha ao atualizar a zona"}), 400

    @zonas_bp.route('/zonas/<int:zona_id>', methods=['DELETE'])
    def deletar_zona(zona_id):
        sucesso = zonas_service.deletar_zona(zona_id)
        
        if sucesso:
            return jsonify({"message": "Zona deletada com sucesso"}), 200
        else:
            return jsonify({"error": "Falha ao deletar a zona"}), 400

    return zonas_bp