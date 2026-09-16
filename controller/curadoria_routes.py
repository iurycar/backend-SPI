from flask import Blueprint, current_app, jsonify, request, render_template, send_file, session
from services.curadoria_service import CuradoriaService
from core.auth import login_required, perfil_required
from schemas.config_dto import ConfigDTO
import os

curadoria_service = CuradoriaService()

curadoria_bp = Blueprint('curadoria', __name__)

@curadoria_bp.route('/curadoria')
@login_required
def index():
    return render_template('curadoria.html')


@curadoria_bp.route('/curadoria/favicon.png')
def favicon():
    caminho_icone = os.path.join(current_app.root_path, 'assets', 'modelo', 'icons.png')
    return send_file(caminho_icone, mimetype='image/png')


@curadoria_bp.route('/api/config', methods=['GET', 'POST'])
@login_required
def gerenciar_config():
    if request.method == 'POST':
        dados = request.json or {}
        if not dados:
            return jsonify({"error": "Dados inválidos"}), 400

        try:
            config = ConfigDTO.from_dict(dados)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        return jsonify(curadoria_service.atualizar_configuracao(config))
    return jsonify(curadoria_service.obter_configuracao())


@curadoria_bp.route('/api/classes', methods=['GET'])
@login_required
def obter_classes():
    classes = curadoria_service.obter_classes()
    return jsonify(classes)


@curadoria_bp.route('/api/samples/count', methods=['GET'])
@login_required
def obter_imagens_total():
    total = curadoria_service.obter_imagens_total()
    return jsonify({"total": total})


@curadoria_bp.route('/api/samples', methods=['GET'])
@login_required
def obter_imagens():
    inicio = request.args.get('start', default=0, type=int)
    fim = request.args.get('end', default=100, type=int)

    if inicio is None or fim is None or inicio < 0 or fim <= inicio:
        return jsonify([])

    imagens = curadoria_service.obter_imagens_lote(inicio, fim)

    return jsonify(imagens)


@curadoria_bp.route('/api/image/<filename>', methods=['GET'])
@login_required
def obter_imagem(filename):
    caminho_imagem = curadoria_service.obter_imagem(filename)

    if not caminho_imagem or not os.path.exists(caminho_imagem):
        return jsonify({"error": "Imagem não encontrada"}), 404

    return send_file(caminho_imagem, mimetype='image/jpeg', max_age=86400)


@curadoria_bp.route('/api/labels/<filename>', methods=['GET'])
@login_required
def obter_labels(filename):
    boxes = curadoria_service.obter_labels(filename)
    return jsonify(boxes)


@curadoria_bp.route('/api/save-and-move', methods=['POST'])
@login_required
def salvar_e_mover():
    dados = request.json or {}
    nome_base = dados.get('id')
    arquivo_imagem = dados.get('image_file')
    arquivo_label = dados.get('label_file')
    boxes = dados.get('boxes', [])
    aplicar_augmentation = dados.get('apply_augmentation', False)
    permitir_val_split = dados.get('allow_validation_split', False)
    split = dados.get('split', None)

    resultado = curadoria_service.salvar_e_mover(
        nome_arquivo=nome_base,
        arquivo_imagem=arquivo_imagem,
        arquivo_label=arquivo_label,
        boxes=boxes,
        aplicar_aug=aplicar_augmentation,
        val_split=permitir_val_split,
        split=split
    )

    return jsonify(resultado)


@curadoria_bp.route('/api/sample/<base_name>', methods=['DELETE'])
@login_required
def deletar_imagem(base_name):
    resultado = curadoria_service.deletar_imagem(base_name)
    return jsonify(resultado)