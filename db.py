"""Conexão com o banco de dados e utilitários relacionados."""

from contextlib import contextmanager

import psycopg2
import psycopg2.extras

import config


@contextmanager
def get_cursor(commit=False):
    """Abre uma conexão e fornece um cursor (RealDictCursor).

    Se commit=True, confirma a transação ao final. Em caso de erro,
    desfaz a transação e propaga a exceção. A conexão é sempre fechada.
    """
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def normalizar_uid(uid: str) -> str:
    """Normaliza UID para o formato 'XX XX XX XX' maiúsculo.

    Aceita tanto "E745D619" quanto "E7 45 D6 19".
    """
    uid = uid.strip().upper()
    partes = uid.split()
    if len(partes) == 1 and len(uid) % 2 == 0:
        partes = [uid[i:i + 2] for i in range(0, len(uid), 2)]
    return " ".join(partes)
