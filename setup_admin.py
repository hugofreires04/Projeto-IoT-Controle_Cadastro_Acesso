"""Gera o hash bcrypt do usuário admin e grava/atualiza o registro no banco.

Uso:
    python setup_admin.py [senha]

Sem argumento, usa a senha padrão "admin123" (a mesma citada na migration).
"""

import sys

import bcrypt

from db import get_cursor

EMAIL_ADMIN = "admin@sistema.com"
NOME_ADMIN = "Administrador"


def main():
    senha = sys.argv[1] if len(sys.argv) > 1 else "admin123"
    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO a3_usuarios (nome, email, senha_hash, nivel_acesso)
               VALUES (%s, %s, %s, 'admin')
               ON CONFLICT (email) DO UPDATE SET senha_hash = EXCLUDED.senha_hash""",
            (NOME_ADMIN, EMAIL_ADMIN, senha_hash)
        )

    print(f"Usuário admin pronto: {EMAIL_ADMIN} / senha: {senha}")


if __name__ == "__main__":
    main()
