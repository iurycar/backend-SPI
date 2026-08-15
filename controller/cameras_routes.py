from services.cameras_service import CamerasService
from services.zonas_service import ZonasService
from flask import Blueprint, jsonify, request

cameras_bp = Blueprint('cameras', __name__)

def create_cameras_bp(connection):
    cameras_service = CamerasService(connection)
    zonas_service = ZonasService(connection)

    @cameras_bp.route('/cameras', methods=['GET'])
    def listar_cameras():
        cameras = cameras_service.listar_cameras()
        return jsonify(cameras), 200

    @cameras_bp.route('/cameras/<int:camera_id>', methods=['GET'])
    def obter_camera_por_id(camera_id):
        camera = cameras_service.obter_camera_por_id(camera_id)
        if camera:
            return jsonify(camera), 200
        else:
            return jsonify({'message': 'Câmera não encontrada'}), 404

    @cameras_bp.route('/cameras/setor/<int:setor_id>', methods=['GET'])
    def listar_cameras_por_setor(setor_id):
        cameras = cameras_service.obter_cameras_por_id_setor(setor_id)
        if cameras:
            return jsonify(cameras), 200
        else:
            return jsonify({'message': 'Nenhuma câmera encontrada para o setor especificado'}), 404

    @cameras_bp.route('/cameras/<int:camera_id>/zonas', methods=['GET'])
    def listar_zonas_por_camera(camera_id):
        zonas = zonas_service.listar_zonas_por_id_camera(camera_id)
        if zonas:
            return jsonify(zonas), 200
        else:
            return jsonify({'message': 'Nenhuma zona encontrada para a câmera especificada'}), 404

    @cameras_bp.route('/cameras/registrar', methods=['POST'])
    def registrar_camera():
        data = request.get_json()

        print(f"Dados recebidos para registrar câmera: {data}")  # Log the received data

        camera = cameras_service.registrar_camera(data)

        if camera:
            return jsonify(camera), 201
        else:
            return jsonify({'message': 'Falha ao registrar a câmera'}), 400

    return cameras_bp