"""Lectura de las sesiones que cada herramienta deja en disco.

Nada de red ni de APIs: se leen los mismos archivos que usan Claude Code, OpenCode
y Codex. Cada lector devuelve ``Uso`` con lo que ese proveedor realmente registra;
lo que no registra queda en ``None`` (no en cero).
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import precios
from .modelo import Uso


def _fecha(valor: object) -> datetime | None:
    if not isinstance(valor, str) or not valor:
        return None
    texto = valor.replace("Z", "+00:00")
    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _ms(valor: object) -> datetime | None:
    if not isinstance(valor, (int, float)) or valor <= 0:
        return None
    return datetime.fromtimestamp(valor / 1000, tz=timezone.utc)


def rutas(base: Path | None = None) -> dict[str, Path]:
    """Dónde vive cada herramienta (respeta las variables de entorno de cada una)."""
    origen = base or Path.home()
    return {
        "claude": Path(os.environ.get("CLAUDE_CONFIG_DIR", origen / ".claude")),
        "opencode": Path(os.environ.get("OPENCODE_DATA_DIR", origen / ".local" / "share" / "opencode")),
        "codex": Path(os.environ.get("CODEX_HOME", origen / ".codex")),
    }


# --- Claude Code --------------------------------------------------------------


def claude(carpeta: Path, tabla: dict[str, dict[str, float]] | None = None) -> list[Uso]:
    """Una fila por (sesión, modelo): los subagentes usan otro modelo dentro de la misma sesión."""
    proyectos = carpeta / "projects"
    if not proyectos.is_dir():
        return []

    usos: list[Uso] = []

    for ruta in sorted(proyectos.rglob("*.jsonl")):
        vistos: set[str] = set()
        acumulado: dict[str, Uso] = {}

        try:
            lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for linea in lineas:
            if '"usage"' not in linea:
                continue
            try:
                evento = json.loads(linea)
            except json.JSONDecodeError:
                continue

            mensaje = evento.get("message") or {}
            uso = mensaje.get("usage")
            if evento.get("type") != "assistant" or not isinstance(uso, dict):
                continue

            # El mismo request aparece en el transcript del padre y en el del
            # subagente: se cuenta una vez por requestId (o uuid si falta).
            clave = evento.get("requestId") or evento.get("uuid") or ""
            if clave and clave in vistos:
                continue
            vistos.add(clave)

            modelo = str(mensaje.get("model") or "desconocido")
            entrada = int(uso.get("input_tokens") or 0)
            salida = int(uso.get("output_tokens") or 0)
            lectura = int(uso.get("cache_read_input_tokens") or 0)
            escritura = int(uso.get("cache_creation_input_tokens") or 0)
            fecha = _fecha(evento.get("timestamp")) or datetime.now(timezone.utc)

            fila = acumulado.setdefault(
                modelo,
                Uso(
                    proveedor="claude",
                    modelo=modelo,
                    sesion=evento.get("sessionId") or ruta.stem,
                    titulo=ruta.parent.name,
                    inicio=fecha,
                ),
            )
            fila.requests += 1
            fila.entrada += entrada
            fila.salida += salida
            fila.cache_lectura += lectura
            fila.cache_escritura += escritura
            fila.fin = fecha

        for fila in acumulado.values():
            fila.costo = precios.costo_de(
                fila.modelo, fila.entrada, fila.salida, fila.cache_lectura, fila.cache_escritura, tabla
            )
            fila.costo_estimado = fila.costo is not None
            usos.append(fila)

    return usos


# --- OpenCode -----------------------------------------------------------------


def opencode(carpeta: Path) -> list[Uso]:
    """OpenCode ya guarda tokens, costo y tiempo activo por sesión: se leen tal cual.

    La base se abre en modo solo lectura: un dashboard no puede dejar un lock ni
    tocar el archivo de otra herramienta.
    """
    base = carpeta / "opencode.db"
    if not base.is_file():
        return []

    try:
        con = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    except sqlite3.Error:
        return []

    try:
        mensajes = {
            sesion: total
            for sesion, total in con.execute(
                "select session_id, count(*) from session_message where type = 'assistant' group by session_id"
            )
        }

        usos: list[Uso] = []
        for fila in con.execute(
            "select id, title, tokens_input, tokens_output, tokens_cache_read, tokens_cache_write, "
            "cost, time_created, time_updated, time_busy, model from session_v2"
        ):
            (
                sesion,
                titulo,
                entrada,
                salida,
                lectura,
                escritura,
                costo,
                creada,
                actualizada,
                ocupado,
                modelo,
            ) = fila

            modelo_json = {}
            try:
                modelo_json = json.loads(modelo) if modelo else {}
            except (TypeError, json.JSONDecodeError):
                modelo_json = {}

            nombre = str(modelo_json.get("modelID") or modelo_json.get("id") or modelo or "desconocido")

            # `time_busy` no es una duración: es el timestamp de la última vez que
            # la sesión estuvo ocupada. El tiempo activo es desde que se creó hasta
            # ese momento (sin contar el rato que quedó abierta sin usarse).
            activo = None
            if isinstance(ocupado, (int, float)) and isinstance(creada, (int, float)) and ocupado > creada:
                activo = (ocupado - creada) / 60000

            usos.append(
                Uso(
                    proveedor="opencode",
                    modelo=nombre,
                    sesion=str(sesion),
                    titulo=str(titulo or ""),
                    inicio=_ms(creada),
                    fin=_ms(actualizada),
                    requests=int(mensajes.get(sesion, 0)),
                    entrada=int(entrada or 0),
                    salida=int(salida or 0),
                    cache_lectura=int(lectura or 0),
                    cache_escritura=int(escritura or 0),
                    costo=float(costo or 0.0),
                    costo_estimado=False,
                    tiempo_activo_min=activo,
                )
            )
        return usos
    except sqlite3.Error:
        return []
    finally:
        con.close()


# --- Codex --------------------------------------------------------------------


def codex(carpeta: Path, tabla: dict[str, dict[str, float]] | None = None) -> list[Uso]:
    """Codex deja tokens acumulados por sesión; el modelo viene del turn_context."""
    sesiones = carpeta / "sessions"
    if not sesiones.is_dir():
        return []

    usos: list[Uso] = []

    for ruta in sorted(sesiones.rglob("*.jsonl")):
        modelo = "desconocido"
        totales = None
        inicio = None
        fin = None
        requests = 0
        identificador = ruta.stem

        try:
            lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for linea in lineas:
            try:
                evento = json.loads(linea)
            except json.JSONDecodeError:
                continue

            tipo = evento.get("type")
            carga = evento.get("payload") or {}
            fecha = _fecha(evento.get("timestamp"))
            if fecha:
                inicio = inicio or fecha
                fin = fecha

            if tipo == "session_meta":
                identificador = str(carga.get("id") or identificador)
            elif tipo == "turn_context":
                modelo = str(carga.get("model") or modelo)
            elif tipo == "response_item" and carga.get("type") == "message":
                if carga.get("role") != "user":
                    requests += 1
            elif tipo == "event_msg" and carga.get("type") == "token_count":
                info = carga.get("info") or {}
                # `total_token_usage` es acumulativo: el último evento es el total.
                if info.get("total_token_usage"):
                    totales = info["total_token_usage"]

        if not totales:
            continue

        entrada = int(totales.get("input_tokens") or 0)
        salida = int(totales.get("output_tokens") or 0)
        lectura = int(totales.get("cached_input_tokens") or 0)
        escritura = int(totales.get("cache_write_input_tokens") or 0)

        usos.append(
            Uso(
                proveedor="codex",
                modelo=modelo,
                sesion=identificador,
                titulo=ruta.parent.name,
                inicio=inicio,
                fin=fin,
                requests=requests,
                entrada=entrada,
                salida=salida,
                cache_lectura=lectura,
                cache_escritura=escritura,
                costo=precios.costo_de(modelo, entrada, salida, lectura, escritura, tabla),
                costo_estimado=precios.costo_de(modelo, entrada, salida, lectura, escritura, tabla)
                is not None,
            )
        )

    return usos


def leer_todo(tabla: dict[str, dict[str, float]] | None = None, base: Path | None = None) -> list[Uso]:
    """Junta las tres fuentes; una carpeta que falta simplemente no aporta."""
    donde = rutas(base)
    usos: list[Uso] = []
    usos += claude(donde["claude"], tabla)
    usos += opencode(donde["opencode"])
    usos += codex(donde["codex"], tabla)
    return usos
