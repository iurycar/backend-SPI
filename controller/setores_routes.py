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

    @setores_bp.route('/setores/registrar', methods=['POST'])
    def registrar_setor():
        data = request.get_json()
        setor = setores_service.registrar_setor(data)

        if setor:
            return jsonify(setor), 201
        else:
            return jsonify({'message': 'Falha ao registrar o setor'}), 400

    @setores_bp.route('/setores/<int:setor_id>', methods=['PUT'])
    def atualizar_setor(setor_id):
        data = request.get_json()
        setor = setores_service.atualizar_setor(setor_id, data)

        if setor:
            return jsonify(setor), 200
        else:
            return jsonify({'message': 'Falha ao atualizar o setor'}), 400

    @setores_bp.route('/setores/<int:setor_id>', methods=['DELETE'])
    def deletar_setor(setor_id):
        sucesso = setores_service.deletar_setor(setor_id)

        if sucesso:
            return jsonify({'message': 'Setor deletado com sucesso'}), 200
        else:
            return jsonify({'message': 'Falha ao deletar o setor'}), 400
    
    return setores_bp