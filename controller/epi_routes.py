from flask import Blueprint, jsonify, request, session
from services.epi_service import EpiService

def create_epi_bp(connection):
    epi_service = EpiService(connection)
    epi_bp = Blueprint('epi_bp', __name__)

    @epi_bp.route('/epis', methods=['GET'])
    def listar_epis():
        epis = epi_service.listar_epis()
        return jsonify(epis), 200

    return epi_bp