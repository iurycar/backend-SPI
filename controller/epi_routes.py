from flask import Blueprint, jsonify, request, session
from services.epi_service import EpiService
from repository.epi_repository import EpiRepository

epi_bp = Blueprint('epi_bp', __name__)

repo = EpiRepository()
service = EpiService(repo)

@epi_bp.route('/epis', methods=['GET'])
def listar_epis():
    epis = service.listar_epis()
    return jsonify(epis), 200