from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_usage import fuentes
from agent_usage.cli import _desde, main
from agent_usage.modelo import Uso, agregar


def test_periodos_validos():
    ahora = datetime(2026, 11, 11, tzinfo=timezone.utc)

    assert _desde("24h", ahora) == ahora.replace(day=10)
    assert _desde("7d", ahora).day == 4
    assert _desde("todo", ahora) is None
    assert _desde("2026-01-01", ahora).year == 2026


def test_periodo_invalido_es_un_error_de_uso():
    with pytest.raises(argparse.ArgumentTypeError):
        _desde("ayer", datetime.now(timezone.utc))


def test_la_cli_lee_las_tres_fuentes_y_sale_con_cero(
    claude: Path, opencode: Path, codex: Path, hogar: Path, monkeypatch, capsys
):
    monkeypatch.setattr(
        fuentes,
        "rutas",
        lambda base=None: {
            "claude": hogar / ".claude",
            "opencode": hogar / ".local" / "share" / "opencode",
            "codex": hogar / ".codex",
        },
    )

    assert main(["--desde", "todo"]) == 0
    salida = capsys.readouterr().out

    assert "Claude Code" in salida
    assert "OpenCode" in salida
    assert "Codex" in salida


def test_la_cli_filtra_por_proveedor(
    claude: Path, opencode: Path, codex: Path, hogar: Path, monkeypatch, capsys
):
    monkeypatch.setattr(
        fuentes,
        "rutas",
        lambda base=None: {
            "claude": hogar / ".claude",
            "opencode": hogar / ".local" / "share" / "opencode",
            "codex": hogar / ".codex",
        },
    )

    assert main(["--desde", "todo", "--proveedor", "codex"]) == 0
    salida = capsys.readouterr().out

    assert "Codex" in salida
    assert "Claude Code" not in salida


def test_la_cli_escribe_csv_y_html(
    claude: Path, opencode: Path, codex: Path, hogar: Path, monkeypatch, tmp_path
):
    monkeypatch.setattr(
        fuentes,
        "rutas",
        lambda base=None: {
            "claude": hogar / ".claude",
            "opencode": hogar / ".local" / "share" / "opencode",
            "codex": hogar / ".codex",
        },
    )
    csv_ruta = tmp_path / "uso.csv"
    html_ruta = tmp_path / "uso.html"

    assert main(["--desde", "todo", "--csv", str(csv_ruta), "--html", str(html_ruta)]) == 0

    assert "proveedor,sesiones" in csv_ruta.read_text(encoding="utf-8")
    assert "<!doctype html>" in html_ruta.read_text(encoding="utf-8")


def test_sin_datos_avisa_y_no_falla(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        fuentes,
        "rutas",
        lambda base=None: {
            "claude": tmp_path / "nada",
            "opencode": tmp_path / "nada2",
            "codex": tmp_path / "nada3",
        },
    )

    assert main([]) == 0
    assert "No hay sesiones" in capsys.readouterr().err


def test_el_agregado_marca_el_costo_incompleto():
    agregados = agregar(
        [
            Uso(proveedor="claude", modelo="m", sesion="1", entrada=10, costo=1.0, costo_estimado=True),
            Uso(proveedor="claude", modelo="m", sesion="2", entrada=10, costo=None),
        ]
    )

    assert agregados[0].costo == 1.0
    assert not agregados[0].costo_completo
