from __future__ import annotations

from pathlib import Path

import pytest

from agent_usage import fuentes


def test_claude_lee_tokens_y_no_cuenta_dos_veces_el_mismo_request(claude: Path, hogar: Path):
    usos = fuentes.claude(hogar / ".claude")

    assert len(usos) == 2  # dos modelos en la misma sesión
    sonnet = next(u for u in usos if u.modelo == "claude-sonnet-5")

    assert sonnet.sesion == "sesion-claude"
    assert sonnet.requests == 1, "el mismo requestId aparecía en el transcript del subagente"
    assert sonnet.entrada == 100
    assert sonnet.salida == 200
    assert sonnet.cache_lectura == 1000
    assert sonnet.cache_escritura == 500
    assert sonnet.costo_estimado
    # 100*2 + 200*10 + 1000*0.2 + 500*2.5, todo por millón.
    assert sonnet.costo == pytest.approx(0.00365)


def test_claude_no_inventa_costo_de_un_modelo_desconocido(claude: Path, hogar: Path):
    ruta = claude
    ruta.write_text(
        '{"type":"assistant","sessionId":"s","requestId":"r1","timestamp":"2026-11-10T10:00:00Z",'
        '"message":{"model":"modelo-inventado","usage":{"input_tokens":10,"output_tokens":10}}}\n',
        encoding="utf-8",
    )

    uso = fuentes.claude(hogar / ".claude")[0]

    assert uso.costo is None
    assert not uso.costo_estimado


def test_claude_sin_carpeta_no_explota(tmp_path: Path):
    assert fuentes.claude(tmp_path / "no-existe") == []


def test_opencode_lee_la_sesion_tal_cual_la_registra(opencode: Path, hogar: Path):
    usos = fuentes.opencode(hogar / ".local" / "share" / "opencode")

    assert len(usos) == 1
    uso = usos[0]
    assert uso.modelo == "kimi-k2.7-code"
    assert uso.tokens == 2000 + 300 + 4000
    assert uso.requests == 2, "sólo los mensajes de tipo assistant"
    assert uso.costo == 0.42, "el costo de OpenCode es el registrado, no una estimación"
    assert not uso.costo_estimado
    assert uso.tiempo_activo_min == 25  # time_busy - time_created


def test_opencode_con_la_base_rota_no_explota(tmp_path: Path):
    carpeta = tmp_path / "opencode"
    carpeta.mkdir()
    (carpeta / "opencode.db").write_bytes(b"no soy una base")

    assert fuentes.opencode(carpeta) == []


def test_codex_usa_el_ultimo_total_acumulado(codex: Path, hogar: Path):
    usos = fuentes.codex(hogar / ".codex")

    assert len(usos) == 1
    uso = usos[0]
    assert uso.modelo == "gpt-5-codex"
    assert uso.entrada == 9000, "el total es el último token_count, no la suma de los eventos"
    assert uso.salida == 1100
    assert uso.cache_lectura == 7000
    assert uso.requests == 2
    assert uso.costo is None, "gpt-5-codex no está en la tabla: mejor 'no se sabe' que cero"
    assert uso.duracion_min == pytest.approx(3.017, abs=0.01)


def test_leer_todo_junta_las_tres_fuentes(claude: Path, opencode: Path, codex: Path, hogar: Path):
    usos = fuentes.leer_todo(base=hogar)

    assert {u.proveedor for u in usos} == {"claude", "opencode", "codex"}
