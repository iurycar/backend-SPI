from flask import Blueprint, jsonify, request, session

# Criação do Blueprint para as rotas
routes_bp = Blueprint('routes', __name__)