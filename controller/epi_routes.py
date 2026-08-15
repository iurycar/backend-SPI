from flask import Blueprint, jsonify, request, session
from services.epi_service import EpiService

def create_epi_bp(connection):
    epi_service = EpiService(connection)
    epi_bp = Blueprint('epi_bp', __name__)

    @epi_bp.route('/epis', methods=['GET'])
    def listar_epis():
        epis = epi_service.listar_epis()
        return jsonify(epis), 200

    @epi_bp.route('/epis/<int:epi_id>', methods=['GET'])
    def obter_epi_por_id(epi_id):
        epi = epi_service.obter_epi_por_id(epi_id)

        if epi:
            return jsonify(epi), 200
        else:
            return jsonify({"error": "EPI não encontrado"}), 404

    return epi_bp