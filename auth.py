"""Autenticacao mockada e geracao/validacao do token SHA-256 usado no handshake gRPC.

Apenas os dois registros de mock_users.json sao validos. O hash de autenticacao
e derivado das credenciais (nao digitado manualmente): cliente e servidor
importam este mesmo modulo, garantindo que ambos calculem hashes identicos.
"""
import hashlib
import json
from pathlib import Path
from typing import Iterable, Optional

MOCK_USERS_PATH = Path(__file__).resolve().parent / "mock_users.json"


def load_mock_users(path: Path = MOCK_USERS_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["users"]


def generate_auth_hash(login: str, senha: str) -> str:
    payload = f"{login}:{senha}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def expected_hashes(users: Optional[Iterable[dict]] = None) -> set[str]:
    users = users if users is not None else load_mock_users()
    return {generate_auth_hash(u["login"], u["senha"]) for u in users}


def is_hash_authorized(received_hash: str, users: Optional[Iterable[dict]] = None) -> bool:
    return received_hash in expected_hashes(users)
