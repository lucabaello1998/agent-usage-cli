"""Fixture: un HOME de mentira con el formato real de cada herramienta."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest


def _iso(momento: datetime) -> str:
    return momento.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture
def hogar(tmp_path: Path) -> Path:
    return tmp_path / "hogar"


@pytest.fixture
def claude(hogar: Path) -> Path:
    proyecto = hogar / ".claude" / "projects" / "c--Users-luca-proyecto"
    proyecto.mkdir(parents=True)

    eventos = [
        {
            "type": "user",
            "timestamp": "2026-11-10T10:00:00.000Z",
            "sessionId": "sesion-claude",
            "message": {"role": "user", "content": "hola"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-11-10T10:00:05.000Z",
            "sessionId": "sesion-claude",
            "requestId": "req_1",
            "message": {
                "model": "claude-sonnet-5",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 200,
                    "cache_read_input_tokens": 1000,
                    "cache_creation_input_tokens": 500,
                },
            },
        },
        # Mismo request repetido (el transcript del padre y el del subagente): no se suma dos veces.
        {
            "type": "assistant",
            "timestamp": "2026-11-10T10:00:05.000Z",
            "sessionId": "sesion-claude",
            "requestId": "req_1",
            "message": {
                "model": "claude-sonnet-5",
                "usage": {"input_tokens": 100, "output_tokens": 200},
            },
        },
        {
            "type": "assistant",
            "timestamp": "2026-11-10T10:01:00.000Z",
            "sessionId": "sesion-claude",
            "requestId": "req_2",
            "message": {
                "model": "claude-haiku-4-5",
                "usage": {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 0},
            },
        },
        {
            "type": "assistant",
            "timestamp": "2026-11-10T10:02:00.000Z",
            "sessionId": "sesion-claude",
            "message": {},
        },
    ]

    archivo = proyecto / "sesion-claude.jsonl"
    archivo.write_text("\n".join(json.dumps(e) for e in eventos) + "\n", encoding="utf-8")
    return archivo


@pytest.fixture
def opencode(hogar: Path) -> Path:
    carpeta = hogar / ".local" / "share" / "opencode"
    carpeta.mkdir(parents=True)
    base = carpeta / "opencode.db"

    con = sqlite3.connect(base)
    con.execute(
        "create table session_v2 (id text, title text, tokens_input int, tokens_output int, "
        "tokens_reasoning int, tokens_cache_read int, tokens_cache_write int, cost real, "
        "time_created int, time_updated int, time_busy int, model text)"
    )
    con.execute("create table session_message (id text, session_id text, type text, data text)")
    creada = 1_762_000_000_000
    con.execute(
        "insert into session_v2 values (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "ses_opencode",
            "Refactor del panel",
            2000,
            300,
            0,
            4000,
            0,
            0.42,
            creada,
            creada + 30 * 60000,
            creada + 25 * 60000,
            json.dumps({"modelID": "kimi-k2.7-code", "providerID": "opencode-go"}),
        ),
    )
    con.executemany(
        "insert into session_message values (?,?,?,?)",
        [
            ("m1", "ses_opencode", "assistant", "{}"),
            ("m2", "ses_opencode", "assistant", "{}"),
            ("m3", "ses_opencode", "user", "{}"),
        ],
    )
    con.commit()
    con.close()
    return base


@pytest.fixture
def codex(hogar: Path) -> Path:
    carpeta = hogar / ".codex" / "sessions" / "2026" / "11" / "09"
    carpeta.mkdir(parents=True)

    eventos = [
        {
            "type": "session_meta",
            "timestamp": "2026-11-09T09:00:00.000Z",
            "payload": {"id": "sesion-codex", "cwd": "C:/proyecto"},
        },
        {
            "type": "turn_context",
            "timestamp": "2026-11-09T09:00:01.000Z",
            "payload": {"model": "gpt-5-codex"},
        },
        {
            "type": "response_item",
            "timestamp": "2026-11-09T09:00:02.000Z",
            "payload": {"type": "message", "role": "assistant", "content": []},
        },
        {
            "type": "event_msg",
            "timestamp": "2026-11-09T09:00:03.000Z",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 5000,
                        "cached_input_tokens": 4000,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 600,
                        "total_tokens": 5600,
                    }
                },
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-11-09T09:03:00.000Z",
            "payload": {"type": "message", "role": "assistant", "content": []},
        },
        {
            "type": "event_msg",
            "timestamp": "2026-11-09T09:03:01.000Z",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 9000,
                        "cached_input_tokens": 7000,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 1100,
                        "total_tokens": 10100,
                    }
                },
            },
        },
    ]

    ruta = carpeta / "rollout-2026-11-09T09-00-00-sesion-codex.jsonl"
    ruta.write_text("\n".join(json.dumps(e) for e in eventos) + "\n", encoding="utf-8")
    return ruta
