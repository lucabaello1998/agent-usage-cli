from __future__ import annotations

import json

import pytest

from agent_usage import precios


def test_precio_de_un_modelo_conocido():
    costo = precios.costo_de("claude-sonnet-5", 1_000_000, 0, 0, 0)

    assert costo == 2.0


def test_el_sufijo_de_fecha_apunta_al_mismo_modelo():
    assert precios.costo_de("claude-sonnet-5-20260101", 1_000_000, 0, 0, 0) == 2.0


def test_un_modelo_desconocido_no_cuesta_cero():
    assert precios.costo_de("modelo-que-no-existe", 1, 1, 1, 1) is None


def test_tabla_propia_desde_json(tmp_path):
    archivo = tmp_path / "precios.json"
    archivo.write_text(
        json.dumps({"modelos": {"mi-modelo": {"input": 1, "output": 2, "read": 0.1, "write5m": 1.5}}}),
        encoding="utf-8",
    )

    tabla = precios.cargar(str(archivo))

    assert precios.costo_de("mi-modelo", 1_000_000, 1_000_000, 0, 0, tabla) == 3.0
    assert precios.costo_de("claude-sonnet-5", 1_000_000, 0, 0, 0, tabla) is None


def test_una_tabla_sin_modelos_es_un_error(tmp_path):
    archivo = tmp_path / "roto.json"
    archivo.write_text('{"otra": 1}', encoding="utf-8")

    with pytest.raises(ValueError, match="modelos"):
        precios.cargar(str(archivo))
