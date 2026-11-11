"""Tabla de precios para estimar el costo de Claude Code.

Tres cosas que conviene tener claras:

- **Es una estimación.** Claude Code con suscripción no factura por token: el
  número sirve para comparar sesiones y modelos entre sí, no como factura.
- **OpenCode no usa esta tabla**: la extensión registra el costo real y el CLI
  lo toma tal cual.
- **Los precios cambian** y no hay un endpoint oficial en JSON. La tabla es una
  foto con fecha; se puede reemplazar con un ``precios.json`` propio
  (``{"modelos": {"claude-sonnet-5": {"input": 2, "output": 10, "read": 0.2,
  "write5m": 2.5}}}``) con ``--precios ruta.json``.

Los valores son los mismos que usa OpenCockpit (misma fuente, una sola foto), en
USD por millón de tokens.
"""

from __future__ import annotations

import json
from pathlib import Path

FECHA_DE_LA_TABLA = "2026-08-30"

# input / output / write5m / read: USD por millón de tokens.
MODELOS: dict[str, dict[str, float]] = {
    "claude-fable-5": {"input": 10, "output": 50, "write5m": 12.5, "read": 1},
    "claude-mythos-5": {"input": 10, "output": 50, "write5m": 12.5, "read": 1},
    "claude-opus-5": {"input": 5, "output": 25, "write5m": 6.25, "read": 0.5},
    "claude-opus-4-8": {"input": 5, "output": 25, "write5m": 6.25, "read": 0.5},
    "claude-opus-4-7": {"input": 5, "output": 25, "write5m": 6.25, "read": 0.5},
    "claude-opus-4-6": {"input": 5, "output": 25, "write5m": 6.25, "read": 0.5},
    "claude-opus-4-5": {"input": 5, "output": 25, "write5m": 6.25, "read": 0.5},
    "claude-sonnet-5": {"input": 2, "output": 10, "write5m": 2.5, "read": 0.2},
    "claude-sonnet-4-6": {"input": 3, "output": 15, "write5m": 3.75, "read": 0.3},
    "claude-sonnet-4-5": {"input": 3, "output": 15, "write5m": 3.75, "read": 0.3},
    "claude-haiku-4-5": {"input": 1, "output": 5, "write5m": 1.25, "read": 0.1},
    "claude-haiku-3-5": {"input": 0.8, "output": 4, "write5m": 1, "read": 0.08},
}


def cargar(ruta: str | None = None) -> dict[str, dict[str, float]]:
    """La tabla incluida, o la del archivo si se pasa uno."""
    if not ruta:
        return MODELOS

    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    modelos = datos.get("modelos") if isinstance(datos, dict) else None
    if not isinstance(modelos, dict) or not modelos:
        raise ValueError(f"{ruta} no tiene un objeto 'modelos' con precios.")

    return {str(nombre): {k: float(v) for k, v in precios.items()} for nombre, precios in modelos.items()}


def costo_de(
    modelo: str,
    entrada: int,
    salida: int,
    cache_lectura: int,
    cache_escritura: int,
    tabla: dict[str, dict[str, float]] | None = None,
) -> float | None:
    """Costo estimado en USD, o ``None`` si el modelo no está en la tabla.

    Devolver ``None`` y no 0 es a propósito: un modelo desconocido no cuesta
    cero, cuesta "no se sabe", y el informe lo tiene que mostrar así.
    """
    tabla = tabla or MODELOS
    precio = tabla.get(modelo)
    if precio is None:
        # Los sufijos de fecha (`claude-sonnet-5-20260101`) apuntan al mismo modelo.
        base = next((clave for clave in tabla if modelo.startswith(clave)), None)
        if base is None:
            return None
        precio = tabla[base]

    return (
        entrada / 1_000_000 * precio.get("input", 0)
        + salida / 1_000_000 * precio.get("output", 0)
        + cache_lectura / 1_000_000 * precio.get("read", 0)
        + cache_escritura / 1_000_000 * precio.get("write5m", 0)
    )
