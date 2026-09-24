"""Identidade NOSTR via chave privada (nsec) lida de uma variavel de ambiente.

Alternativa mais simples ao NIP-46 (Nostr Connect) para uso em scripts locais e em
Codespaces, onde depender de um bunker remoto (com possiveis relays pagos ou fora do
ar) nao compensa: a chave privada e carregada uma unica vez, em memoria, no processo
local, e usada para assinar diretamente os eventos NIP-29 (ver nostr_groups.py). Fica
de fora do repositorio -- deve vir de um arquivo `.env` (nao versionado) ou de uma
variavel de ambiente ja exportada no shell/Codespace.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from nostr_sdk import Keys, PublicKey

DEFAULT_ENV_VAR = "TREINAI_NSEC"
PUBKEY_ENV_VAR = "TREINAI_NPUB"


@dataclass
class AppIdentity:
    """Identidade NOSTR do usuario logado nesta instancia (cliente ou servidor)."""

    signer: Keys
    pubkey_hex: str


def load_identity_from_env(env_var: str = DEFAULT_ENV_VAR) -> AppIdentity:
    """Carrega a nsec (hex ou bech32 `nsec1...`) da variavel de ambiente `env_var`.

    Tambem carrega um arquivo `.env` na raiz do projeto, se existir, antes de ler a
    variavel -- assim `TREINAI_NSEC=nsec1...` num `.env` local funciona sem precisar
    exportar nada manualmente no shell.
    """
    load_dotenv()
    nsec = os.environ.get(env_var, "").strip()
    if not nsec:
        raise RuntimeError(
            f"Variavel de ambiente {env_var} nao definida. Crie um arquivo .env "
            f"(veja .env.example) com {env_var}=nsec1... ou exporte-a no shell."
        )
    keys = Keys.parse(nsec)
    return AppIdentity(signer=keys, pubkey_hex=keys.public_key().to_hex())


def login_with_keys(public_key: str, private_key: str) -> AppIdentity:
    """Login simples (provisorio): recebe a chave publica (npub ou hex) e a privada (nsec
    ou hex) digitadas pelo usuario, confere se a privada gera essa publica e guarda as
    duas em `os.environ` (TREINAI_NPUB / TREINAI_NSEC). Isso vale so para este processo
    -- nada e gravado no `.env` nem em disco, e some ao fechar o app.
    """
    try:
        pubkey = PublicKey.parse(public_key.strip())
    except Exception as exc:
        raise ValueError(f"Chave publica invalida: {exc}") from exc
    try:
        keys = Keys.parse(private_key.strip())
    except Exception as exc:
        raise ValueError(f"Chave privada invalida: {exc}") from exc
    if keys.public_key().to_hex() != pubkey.to_hex():
        raise ValueError("A chave privada nao corresponde a chave publica informada.")

    os.environ[PUBKEY_ENV_VAR] = pubkey.to_bech32()
    os.environ[DEFAULT_ENV_VAR] = keys.secret_key().to_bech32()
    return AppIdentity(signer=keys, pubkey_hex=pubkey.to_hex())
