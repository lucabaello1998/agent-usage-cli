"""Modelo de datos: una fila por sesión y su agregado por proveedor."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Uso:
    """Lo que una sesión consumió, normalizado entre proveedores.

    No todos los proveedores dan lo mismo: OpenCode registra el costo real y el
    tiempo activo; Claude Code da los tokens de cada request (el costo se estima
    con una tabla) y Codex da tokens acumulados por sesión. Los campos que un
    proveedor no expone quedan en ``None`` en vez de en cero, para que el informe
    no invente un dato.
    """

    proveedor: str
    modelo: str
    sesion: str
    titulo: str = ""
    inicio: datetime | None = None
    fin: datetime | None = None
    requests: int = 0
    entrada: int = 0
    salida: int = 0
    cache_lectura: int = 0
    cache_escritura: int = 0
    costo: float | None = None
    costo_estimado: bool = False
    tiempo_activo_min: float | None = None

    @property
    def tokens(self) -> int:
        return self.entrada + self.salida + self.cache_lectura + self.cache_escritura

    @property
    def duracion_min(self) -> float | None:
        if not self.inicio or not self.fin:
            return None
        return max(0.0, (self.fin - self.inicio).total_seconds() / 60)

    @property
    def tiempo_min(self) -> float | None:
        """Tiempo activo si el proveedor lo registra; si no, la duración de la sesión."""
        return self.tiempo_activo_min if self.tiempo_activo_min is not None else self.duracion_min


@dataclass
class Agregado:
    proveedor: str
    sesiones: int = 0
    requests: int = 0
    entrada: int = 0
    salida: int = 0
    cache_lectura: int = 0
    cache_escritura: int = 0
    costo: float = 0.0
    costo_completo: bool = True
    tiempo_min: float = 0.0
    modelos: dict[str, int] = field(default_factory=dict)

    @property
    def tokens(self) -> int:
        return self.entrada + self.salida + self.cache_lectura + self.cache_escritura

    @property
    def tokens_por_request(self) -> float | None:
        return self.tokens / self.requests if self.requests else None


def agregar(usos: list[Uso]) -> list[Agregado]:
    """Suma las sesiones por proveedor."""
    por_proveedor: dict[str, Agregado] = {}

    for uso in usos:
        fila = por_proveedor.setdefault(uso.proveedor, Agregado(proveedor=uso.proveedor))
        fila.sesiones += 1
        fila.requests += uso.requests
        fila.entrada += uso.entrada
        fila.salida += uso.salida
        fila.cache_lectura += uso.cache_lectura
        fila.cache_escritura += uso.cache_escritura
        fila.modelos[uso.modelo] = fila.modelos.get(uso.modelo, 0) + 1

        if uso.costo is None:
            fila.costo_completo = False
        else:
            fila.costo += uso.costo

        if uso.tiempo_min:
            fila.tiempo_min += uso.tiempo_min

    return sorted(por_proveedor.values(), key=lambda a: a.tokens, reverse=True)
