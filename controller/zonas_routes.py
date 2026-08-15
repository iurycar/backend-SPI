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

    return zonas_bp