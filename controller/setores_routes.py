from flask import Blueprint, jsonify, request, session
from services.setores_service import SetoresService

setores_bp = Blueprint('setores', __name__)

def create_setores_bp(connection):
    setores_service = SetoresService(connection)

    @setores_bp.route('/setores', methods=['GET'])
    def listar_setores():
        setores = setores_service.listar_setores()
        return jsonify(setores), 200

    @setores_bp.route('/setores/<int:setor_id>', methods=['GET'])
    def obter_setor_por_id(setor_id):
        setor = setores_service.obter_setor_por_id(setor_id)
        if setor:
            return jsonify(setor), 200
        else:
            return jsonify({'message': 'Setor não encontrado'}), 404

    @setores_bp.route('/setores/responsavel/<int:usuario_id>', methods=['GET'])
    def listar_setores_por_responsavel(usuario_id):
        setores = setores_service.listar_setores_por_id_responsavel(usuario_id)
        return jsonify(setores), 200
    
    return setores_bp