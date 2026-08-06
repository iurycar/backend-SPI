from flask import Flask, request, jsonify, Blueprint, session
from controller.epi_routes import epi_bp

app = Flask(__name__)
app.register_blueprint(epi_bp)

if __name__ == '__main__':
    app.run(debug=True)