"""Autenticacao via NOSTR NIP-46 (Nostr Connect): obtem um signer remoto (bunker) e a
chave publica do usuario logado, usada como identidade em toda a aplicacao -- ao
invés de login/senha mockados. Suporta os dois fluxos de pareamento com o bunker:

- `connect_bunker`: o usuario cola uma connection string `bunker://...` ja emitida
  pelo signer remoto (fluxo iniciado pelo bunker).
- `build_nostrconnect_uri` + `await_nostrconnect`: o app gera uma URI
  `nostrconnect://...` (exibida como QR code) e aguarda o signer remoto escanea-la
  e aprovar a conexao (fluxo iniciado pelo app).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import quote

from nostr_sdk import Keys, NostrConnect, NostrConnectUri

APP_NAME = "TreinAI"
DEFAULT_TIMEOUT = timedelta(seconds=120)


@dataclass
class AppIdentity:
    """Identidade NOSTR do usuario logado nesta instancia (cliente ou servidor)."""

    signer: NostrConnect
    pubkey_hex: str


async def connect_bunker(bunker_uri: str, timeout: timedelta = DEFAULT_TIMEOUT) -> AppIdentity:
    """Conecta a um bunker remoto a partir de uma connection string bunker://...
    (fluxo iniciado pelo bunker: o usuario ja aprovou essa conexao do lado do signer)."""
    uri = NostrConnectUri.parse(bunker_uri)
    app_keys = Keys.generate()
    signer = NostrConnect(uri, app_keys, timeout, None)
    pubkey = await signer.get_public_key_async()
    if pubkey is None:
        raise RuntimeError("O bunker nao respondeu com uma chave publica.")
    return AppIdentity(signer=signer, pubkey_hex=pubkey.to_hex())


def build_nostrconnect_uri(relay_url: str, app_keys: Keys) -> str:
    """Monta a URI nostrconnect://... (fluxo iniciado pelo app) a ser exibida como QR
    para um signer remoto escanear e aprovar."""
    secret = secrets.token_hex(16)
    app_pubkey = app_keys.public_key().to_hex()
    return (
        f"nostrconnect://{app_pubkey}"
        f"?relay={quote(relay_url, safe='')}"
        f"&secret={secret}"
        f"&name={quote(APP_NAME)}"
    )


async def await_nostrconnect(uri: str, app_keys: Keys, timeout: timedelta = DEFAULT_TIMEOUT) -> AppIdentity:
    """Aguarda um signer remoto aprovar a URI nostrconnect://... gerada por
    `build_nostrconnect_uri` (fluxo iniciado pelo app, via QR code)."""
    parsed = NostrConnectUri.parse(uri)
    signer = NostrConnect(parsed, app_keys, timeout, None)
    pubkey = await signer.get_public_key_async()
    if pubkey is None:
        raise RuntimeError("Nenhum bunker aprovou a conexao dentro do tempo limite.")
    return AppIdentity(signer=signer, pubkey_hex=pubkey.to_hex())
