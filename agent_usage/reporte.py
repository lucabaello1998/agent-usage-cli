"""Salidas: tabla para la terminal, CSV para Excel y HTML para compartir."""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import datetime

from . import precios
from .modelo import Agregado, Uso

NOMBRES = {"claude": "Claude Code", "opencode": "OpenCode", "codex": "Codex"}


def _miles(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _dinero(valor: float | None) -> str:
    if valor is None:
        return "—"
    return f"US$ {valor:,.2f}".replace(",", "·").replace(".", ",").replace("·", ".")


def _tiempo(minutos: float) -> str:
    if minutos <= 0:
        return "—"
    if minutos < 60:
        return f"{minutos:.0f} min"
    horas = minutos / 60
    return f"{horas:.1f} h".replace(".", ",")


def tabla(agregados: list[Agregado], detalle: list[Uso] | None = None) -> str:
    if not agregados:
        return "No hay sesiones en el período."

    filas: list[list[str]] = []
    for a in agregados:
        costo = "—" if not a.costo_completo and a.costo == 0 else _dinero(a.costo)
        if not a.costo_completo and a.costo > 0:
            costo = ">= " + _dinero(a.costo)
        filas.append(
            [
                NOMBRES.get(a.proveedor, a.proveedor),
                _miles(a.sesiones),
                _miles(a.requests),
                _miles(a.tokens),
                _miles(a.entrada),
                _miles(a.salida),
                _miles(a.cache_lectura + a.cache_escritura),
                costo,
                _tiempo(a.tiempo_min),
            ]
        )

    encabezado = ["PROVEEDOR", "SESIONES", "REQS", "TOKENS", "ENTRADA", "SALIDA", "CACHÉ", "COSTO", "TIEMPO"]
    anchos = [max(len(fila[i]) for fila in filas + [encabezado]) for i in range(len(encabezado))]
    anchos[0] = max(anchos[0], 11)

    def linea(valores: list[str]) -> str:
        return "  ".join(
            valor.rjust(anchos[i]) if i else valor.ljust(anchos[i]) for i, valor in enumerate(valores)
        )

    salida = [linea(encabezado), "  ".join("-" * ancho for ancho in anchos)]
    salida += [linea(fila) for fila in filas]

    total = sum(a.tokens for a in agregados)
    salida.append("")
    salida.append(f"total: {_miles(total)} tokens en {sum(a.sesiones for a in agregados)} sesiones")

    if detalle:
        salida.append("")
        salida.append("sesiones (más recientes primero):")
        for uso in sorted(detalle, key=lambda u: u.fin or datetime.min, reverse=True)[:15]:
            cuando = uso.fin or uso.inicio
            fecha = cuando.strftime("%d/%m %H:%M") if cuando else "—"
            salida.append(
                f"  {fecha}  {NOMBRES.get(uso.proveedor, uso.proveedor):<11} {uso.modelo[:26]:<26} "
                f"{_miles(uso.tokens):>12} tokens  {uso.titulo[:34]}"
            )

    return "\n".join(salida)


def a_csv(agregados: list[Agregado]) -> str:
    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\n")
    escritor.writerow(
        [
            "proveedor",
            "sesiones",
            "requests",
            "tokens",
            "entrada",
            "salida",
            "cache",
            "costo_usd",
            "tiempo_min",
        ]
    )
    for a in agregados:
        escritor.writerow(
            [
                a.proveedor,
                a.sesiones,
                a.requests,
                a.tokens,
                a.entrada,
                a.salida,
                a.cache_lectura + a.cache_escritura,
                "" if not a.costo_completo and a.costo == 0 else f"{a.costo:.4f}",
                round(a.tiempo_min, 1),
            ]
        )
    return buffer.getvalue()


def a_json(agregados: list[Agregado]) -> str:
    return json.dumps(
        [
            {
                "proveedor": a.proveedor,
                "sesiones": a.sesiones,
                "requests": a.requests,
                "tokens": a.tokens,
                "entrada": a.entrada,
                "salida": a.salida,
                "cache": a.cache_lectura + a.cache_escritura,
                "costo_usd": None if not a.costo_completo and a.costo == 0 else round(a.costo, 4),
                "tiempo_min": round(a.tiempo_min, 1),
                "modelos": a.modelos,
            }
            for a in agregados
        ],
        ensure_ascii=False,
        indent=2,
    )


def a_html(agregados: list[Agregado], desde: str, hasta: str) -> str:
    """Informe para abrir y compartir: sin CDN, sin JS, todo en un archivo."""
    total_tokens = sum(a.tokens for a in agregados) or 1
    total_costo = sum(a.costo for a in agregados)

    tarjetas = "".join(
        f"""
        <article class="tarjeta">
          <header>
            <span class="punto" style="background:{_color(a.proveedor)}"></span>
            <h2>{html.escape(NOMBRES.get(a.proveedor, a.proveedor))}</h2>
          </header>
          <p class="grande">{_miles(a.tokens)} <small>tokens</small></p>
          <p class="modelos">{html.escape(_modelos(a))}</p>
          <div class="barra"><i style="width:{a.tokens / total_tokens * 100:.1f}%;background:{_color(a.proveedor)}"></i></div>
          <dl>
            <div><dt>Sesiones</dt><dd>{_miles(a.sesiones)}</dd></div>
            <div><dt>Requests</dt><dd>{_miles(a.requests)}</dd></div>
            <div><dt>Salida</dt><dd>{_miles(a.salida)}</dd></div>
            <div><dt>Costo</dt><dd>{_dinero(a.costo) if a.costo_completo or a.costo else "—"}</dd></div>
            <div><dt>Tiempo</dt><dd>{_tiempo(a.tiempo_min)}</dd></div>
          </dl>
        </article>"""
        for a in agregados
    )

    filas = "".join(
        f"<tr><td>{html.escape(NOMBRES.get(a.proveedor, a.proveedor))}</td><td>{_miles(a.sesiones)}</td>"
        f"<td>{_miles(a.requests)}</td><td>{_miles(a.tokens)}</td><td>{_miles(a.entrada)}</td>"
        f"<td>{_miles(a.salida)}</td><td>{_miles(a.cache_lectura + a.cache_escritura)}</td>"
        f"<td>{_dinero(a.costo) if a.costo_completo or a.costo else '—'}</td><td>{_tiempo(a.tiempo_min)}</td></tr>"
        for a in agregados
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent usage — {html.escape(desde)} a {html.escape(hasta)}</title>
<style>
  :root {{ color-scheme: dark; --fondo:#0d1117; --panel:#151b24; --borde:#243040; --texto:#e6edf3; --apagado:#8b98a8; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:40px 24px; background:var(--fondo); color:var(--texto);
         font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
  main {{ max-width: 980px; margin: 0 auto; }}
  h1 {{ font-size: 1.7rem; margin: 0 0 4px; letter-spacing: -0.02em; }}
  .sub {{ color: var(--apagado); margin: 0 0 28px; font-size: .9rem; }}
  .tarjetas {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin-bottom: 28px; }}
  .tarjeta {{ background: var(--panel); border: 1px solid var(--borde); border-radius: 14px; padding: 16px 18px; }}
  .tarjeta header {{ display: flex; align-items: center; gap: 8px; }}
  .tarjeta h2 {{ font-size: .95rem; margin: 0; font-weight: 600; }}
  .punto {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
  .grande {{ font-size: 1.85rem; font-weight: 700; margin: 10px 0 8px; letter-spacing: -0.03em; }}
  .grande small {{ font-size: .7rem; color: var(--apagado); font-weight: 500; }}
  .modelos {{ margin: 0 0 10px; font-size: .74rem; color: var(--apagado); }}
  .barra {{ height: 6px; background: #0b1118; border-radius: 999px; overflow: hidden; margin-bottom: 14px; }}
  .barra i {{ display: block; height: 100%; border-radius: 999px; }}
  dl {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px; margin: 0; }}
  dt {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .06em; color: var(--apagado); }}
  dd {{ margin: 0; font-variant-numeric: tabular-nums; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .88rem; background: var(--panel);
           border: 1px solid var(--borde); border-radius: 14px; overflow: hidden; }}
  th, td {{ padding: 10px 12px; text-align: right; font-variant-numeric: tabular-nums; }}
  th:first-child, td:first-child {{ text-align: left; }}
  thead th {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .06em; color: var(--apagado);
              border-bottom: 1px solid var(--borde); }}
  tbody tr + tr td {{ border-top: 1px solid #1b2430; }}
  footer {{ color: var(--apagado); font-size: .78rem; margin-top: 22px; line-height: 1.6; }}
  footer code {{ background: #0b1118; padding: 1px 5px; border-radius: 5px; }}
</style>
</head>
<body>
<main>
  <h1>Uso de agentes de IA</h1>
  <p class="sub">{html.escape(desde)} → {html.escape(hasta)} · {_miles(sum(a.tokens for a in agregados))} tokens
     · {_dinero(total_costo)} estimado</p>

  <section class="tarjetas">{tarjetas}</section>

  <table>
    <thead><tr><th>Proveedor</th><th>Sesiones</th><th>Reqs</th><th>Tokens</th><th>Entrada</th>
      <th>Salida</th><th>Caché</th><th>Costo</th><th>Tiempo</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>

  <footer>
    Leído de los archivos locales de cada herramienta: <code>~/.claude</code>,
    <code>~/.local/share/opencode/opencode.db</code> y <code>~/.codex/sessions</code>.
    El costo de Claude y Codex es una estimación con la tabla del {precios.FECHA_DE_LA_TABLA}
    (USD por millón de tokens); el de OpenCode es el que registra la propia herramienta.
    Nada sale de la máquina.
  </footer>
</main>
</body>
</html>
"""


def _color(proveedor: str) -> str:
    return {"claude": "#d97757", "opencode": "#38bdf8", "codex": "#10a37f"}.get(proveedor, "#8b98a8")


def _modelos(agregado: Agregado, maximo: int = 3) -> str:
    """Los modelos usados, sin los sintéticos ni la lista interminable."""
    nombres = [n for n in agregado.modelos if n and not n.startswith("<")]
    nombres.sort()
    if not nombres:
        return "—"
    visibles = nombres[:maximo]
    resto = len(nombres) - len(visibles)
    return ", ".join(visibles) + (f" y {resto} más" if resto > 0 else "")
