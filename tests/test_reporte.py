from __future__ import annotations

import csv
import io

from agent_usage import reporte
from agent_usage.modelo import Uso, agregar


def _usos() -> list[Uso]:
    return [
        Uso(
            proveedor="claude",
            modelo="claude-sonnet-5",
            sesion="s1",
            titulo="Proyecto <script>alert(1)</script>",
            requests=10,
            entrada=1000,
            salida=200,
            cache_lectura=5000,
            cache_escritura=100,
            costo=0.05,
            costo_estimado=True,
        ),
        Uso(
            proveedor="codex",
            modelo="gpt-5-codex",
            sesion="s2",
            requests=3,
            entrada=500,
            salida=50,
            costo=None,
        ),
    ]


def test_la_tabla_muestra_proveedores_y_totales():
    texto = reporte.tabla(agregar(_usos()))

    assert "Claude Code" in texto
    assert "Codex" in texto
    assert "total:" in texto
    assert "6.850" in texto  # 1000+200+5000+100 (Claude) + 500+50 (Codex)


def test_un_costo_incompleto_se_marca_y_no_se_inventa():
    texto = reporte.tabla(agregar(_usos()))

    assert "US$ 0,05" in texto
    assert "—" in texto  # Codex sin precio: guion, no cero


def test_el_csv_se_puede_leer():
    filas = list(csv.DictReader(io.StringIO(reporte.a_csv(agregar(_usos())))))

    assert {f["proveedor"] for f in filas} == {"claude", "codex"}
    assert filas[0]["tokens"] == "6300"


def test_el_html_escapa_lo_que_viene_de_las_sesiones():
    usos = _usos()
    usos.append(
        Uso(proveedor="claude", modelo="modelo<script>alert(1)</script>", sesion="s3", entrada=1, costo=0.0)
    )

    html = reporte.a_html(agregar(usos), "2026-11-01", "2026-11-11")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "cdn" not in html.lower()  # el informe no carga recursos de afuera
