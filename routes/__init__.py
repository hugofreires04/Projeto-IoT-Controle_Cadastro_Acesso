"""routes/ — Pacote com todas as rotas da API REST, separadas por domínio.

Cada módulo define um Blueprint do Flask com prefixo /api:
  auth_routes   → login/logout/me (sessões)
  funcionarios  → cadastro e listagem de funcionários e seus cartões
  cadastros     → lugares (áreas), usuários do painel e fila de UIDs pendentes
  acessos       → listagem/estatísticas/CSV + endpoints consumidos pelo Node-RED
"""

from .acessos import bp as acessos_bp
from .auth_routes import bp as auth_routes_bp
from .cadastros import bp as cadastros_bp
from .funcionarios import bp as funcionarios_bp


def registrar_rotas(app):
    """Registra todos os blueprints na aplicação Flask (chamado pelo app.py)."""
    app.register_blueprint(auth_routes_bp)
    app.register_blueprint(funcionarios_bp)
    app.register_blueprint(cadastros_bp)
    app.register_blueprint(acessos_bp)
