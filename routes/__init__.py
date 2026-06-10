from .api_acesso import bp as api_acesso_bp
from .api_funcionarios import bp as api_funcionarios_bp
from .painel import bp as painel_bp


def registrar_rotas(app):
    app.register_blueprint(api_funcionarios_bp)
    app.register_blueprint(api_acesso_bp)
    app.register_blueprint(painel_bp)
