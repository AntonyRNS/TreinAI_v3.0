"""Operacoes NIP-29 (grupos baseados em relay) usadas pelo TreinAI: o servidor
publica seu endereco gRPC no grupo (kind 30078, dado de app replaceable via NIP-78)
para que o cliente o descubra; a autorizacao de quem pode treinar e decidida pela
lista de membros do grupo (kind 9000 = adicionado, kind 9001 = removido), no lugar
do login/senha mockados e do hash SHA-256 que existiam em auth.py.
"""
from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Callable, Optional

from nostr_sdk import (
    Client,
    EventBuilder,
    Filter,
    Kind,
    NostrConnect,
    PublicKey,
    RelayUrl,
    ReqTarget,
    SingleLetterTag,
    Tag,
)

SERVER_ADDRESS_KIND = Kind(30078)
SERVER_ADDRESS_IDENTIFIER = "treinai-server-address"
MEMBER_ADDED_KIND = Kind(9000)
MEMBER_REMOVED_KIND = Kind(9001)
MEMBERSHIP_KINDS = [MEMBER_ADDED_KIND, MEMBER_REMOVED_KIND]

_H_TAG = SingleLetterTag.from_byte(ord("h"))

CONNECT_TIMEOUT = timedelta(seconds=10)
FETCH_TIMEOUT = timedelta(seconds=10)


async def _connected_client(relay_url: str) -> Client:
    client = Client()
    await client.add_relay(RelayUrl.parse(relay_url))
    await client.connect(and_wait=CONNECT_TIMEOUT)
    return client


async def fetch_server_address(relay_url: str, group_id: str) -> Optional[str]:
    """Busca, no grupo declarado, o evento mais recente publicado por
    `publish_server_address` e devolve o endereco "host:port", ou None se o
    servidor ainda nao publicou nenhum endereco nesse grupo."""
    client = await _connected_client(relay_url)
    try:
        f = (
            Filter()
            .kind(SERVER_ADDRESS_KIND)
            .identifier(SERVER_ADDRESS_IDENTIFIER)
            .custom_tag(_H_TAG, group_id)
            .limit(10)
        )
        events = await client.fetch_events(ReqTarget.auto([f]), timeout=FETCH_TIMEOUT)
        if not events:
            return None
        latest = max(events, key=lambda e: e.created_at().as_secs())
        payload = json.loads(latest.content())
        return f"{payload['host']}:{payload['port']}"
    finally:
        await client.disconnect()


async def publish_server_address(relay_url: str, signer: NostrConnect, group_id: str, address: str) -> None:
    """Assina (via NIP-46) e publica no grupo o endereco "host:port" em que o
    servidor central esta escutando."""
    host, port = address.rsplit(":", 1)
    content = json.dumps({"host": host, "port": int(port)})
    client = await _connected_client(relay_url)
    try:
        builder = EventBuilder(SERVER_ADDRESS_KIND, content).tags(
            [Tag.identifier(SERVER_ADDRESS_IDENTIFIER), Tag.custom("h", [group_id])]
        )
        event = await builder.finalize_async(signer)
        await client.send_event(event)
    finally:
        await client.disconnect()


async def check_membership(relay_url: str, group_id: str, pubkey_hex: str) -> bool:
    """Verifica se `pubkey_hex` e atualmente membro do grupo: conforme a NIP-29, o
    mais recente entre kind:9000 (adicionado) e kind:9001 (removido) decide."""
    client = await _connected_client(relay_url)
    try:
        pubkey = PublicKey.parse(pubkey_hex)
        f = (
            Filter()
            .kinds(MEMBERSHIP_KINDS)
            .custom_tag(_H_TAG, group_id)
            .pubkey(pubkey)
            .limit(10)
        )
        events = await client.fetch_events(ReqTarget.auto([f]), timeout=FETCH_TIMEOUT)
        if not events:
            return False
        latest = max(events, key=lambda e: e.created_at().as_secs())
        return latest.kind().as_u16() == MEMBER_ADDED_KIND.as_u16()
    finally:
        await client.disconnect()


async def watch_membership(
    relay_url: str,
    group_id: str,
    on_update: Callable[[str, bool, int], None],
    should_stop: Callable[[], bool],
) -> None:
    """Mantem uma assinatura viva ao grupo e chama `on_update(pubkey_hex, is_member,
    created_at)` para cada evento kind:9000/9001 (estado inicial + novos eventos),
    ate que `should_stop()` retorne True. Usado pelo MembershipWatcher do servidor
    para autorizar clientes sem precisar de uma consulta de rede a cada handshake."""
    client = await _connected_client(relay_url)
    try:
        f = Filter().kinds(MEMBERSHIP_KINDS).custom_tag(_H_TAG, group_id)

        for event in await client.fetch_events(ReqTarget.auto([f]), timeout=FETCH_TIMEOUT):
            on_update(event.author().to_hex(), event.kind().as_u16() == MEMBER_ADDED_KIND.as_u16(), event.created_at().as_secs())

        await client.subscribe(ReqTarget.auto([f]))
        stream = client.notifications()
        while not should_stop():
            try:
                item = await asyncio.wait_for(stream.next(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if item is None:
                break
            if item.is_NEW_EVENT():
                event = item.event
                on_update(event.author().to_hex(), event.kind().as_u16() == MEMBER_ADDED_KIND.as_u16(), event.created_at().as_secs())
    finally:
        await client.disconnect()
