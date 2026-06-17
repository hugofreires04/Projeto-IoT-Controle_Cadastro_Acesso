from .acessos import bp as acessos_bp
from .auth_routes import bp as auth_routes_bp
from .cadastro import bp as cadastro_bp
from .funcionarios import bp as funcionarios_bp


def registrar_rotas(app):
    app.register_blueprint(auth_routes_bp)
    app.register_blueprint(funcionarios_bp)
    app.register_blueprint(acessos_bp)
    app.register_blueprint(cadastro_bp)
