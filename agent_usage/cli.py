"""CLI: `agent-usage` (tabla), `--csv`, `--html`, `--json`."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__, fuentes, precios, reporte
from .modelo import agregar


def _desde(texto: str, ahora: datetime) -> datetime | None:
    """``24h``, ``7d``, ``30d``, ``todo`` o una fecha ``AAAA-MM-DD``."""
    if texto.lower() in ("todo", "all", "0"):
        return None

    unidad = re.fullmatch(r"(\d+)\s*([hdw])", texto.lower().strip())
    if unidad:
        cantidad, escala = int(unidad.group(1)), unidad.group(2)
        delta = {
            "h": timedelta(hours=cantidad),
            "d": timedelta(days=cantidad),
            "w": timedelta(weeks=cantidad),
        }[escala]
        return ahora - delta

    try:
        return datetime.strptime(texto, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"No entiendo el período '{texto}'. Probá 24h, 7d, 30d, todo o AAAA-MM-DD."
        ) from None


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-usage",
        description="Uso de Claude Code, OpenCode y Codex desde los archivos locales: tokens, costo y tiempo.",
    )
    parser.add_argument("--desde", default="7d", help="período: 24h, 7d, 30d, todo o AAAA-MM-DD (default 7d)")
    parser.add_argument("--proveedor", choices=["claude", "opencode", "codex"], help="una sola herramienta")
    parser.add_argument("--detalle", action="store_true", help="listar también las sesiones")
    parser.add_argument("--csv", metavar="RUTA", help="escribir CSV")
    parser.add_argument("--html", metavar="RUTA", help="escribir un informe HTML autocontenido")
    parser.add_argument("--json", action="store_true", help="imprimir JSON por stdout")
    parser.add_argument("--precios", metavar="RUTA", help="tabla de precios propia (JSON)")
    parser.add_argument("--sin-precios", action="store_true", help="no estimar costos: sólo tokens")
    parser.add_argument("--version", action="version", version=f"agent-usage {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows sigue abriendo la consola en cp1252: sin esto, un carácter como "≥"
    # corta el informe a la mitad.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = construir_parser()
    args = parser.parse_args(argv)

    ahora = datetime.now(timezone.utc)
    try:
        desde = _desde(args.desde, ahora)
    except argparse.ArgumentTypeError as error:
        parser.error(str(error))

    tabla = None if args.sin_precios else precios.cargar(args.precios)
    usos = fuentes.leer_todo(tabla)

    if desde:
        usos = [u for u in usos if (u.fin or u.inicio or ahora) >= desde]

    if args.proveedor:
        usos = [u for u in usos if u.proveedor == args.proveedor]

    if not usos:
        print("No hay sesiones en el período.", file=sys.stderr)
        print(
            "Se leen ~/.claude/projects, ~/.local/share/opencode/opencode.db y ~/.codex/sessions. "
            "Si usás esas herramientas, probá con --desde todo.",
            file=sys.stderr,
        )
        return 0

    agregados = agregar(usos)
    etiqueta_desde = desde.strftime("%Y-%m-%d") if desde else "el principio"
    etiqueta_hasta = ahora.strftime("%Y-%m-%d")

    if args.json:
        print(reporte.a_json(agregados))
    else:
        print(reporte.tabla(agregados, usos if args.detalle else None))

    if args.csv:
        ruta = Path(args.csv)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        # BOM: Excel abre los acentos bien si el archivo es UTF-8 con BOM.
        ruta.write_text("\ufeff" + reporte.a_csv(agregados), encoding="utf-8")
        print(f"\ncsv: {ruta}", file=sys.stderr)

    if args.html:
        ruta = Path(args.html)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(reporte.a_html(agregados, etiqueta_desde, etiqueta_hasta), encoding="utf-8")
        print(f"html: {ruta}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
