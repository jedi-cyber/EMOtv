"""Cupos del servidor para la lectura en vivo y la actividad.

- Sesiones activas: como máximo MAX_ACTIVE_SESSIONS conexiones analizan a la vez.
- Análisis simultáneos: como máximo MAX_CONCURRENT_ANALYSES cuadros se analizan
  a la vez, en un pool de hilos propio, fuera del bucle de eventos. Así el
  login, la API y el chat siguen respondiendo aunque el análisis esté saturado.

Si no hay cupo, se espera ANALYSIS_BUSY_WAIT_SECONDS; después se informa que el
servidor está ocupado. Los cupos son por proceso: con varios workers de uvicorn,
cada uno tiene los suyos.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import TypeVar

from emotv.config import ServerLoadSettings

T = TypeVar("T")

SERVER_BUSY_MESSAGE = "El servidor está ocupado; intenta de nuevo en un momento"
# Código de cierre estándar de WebSocket "Try Again Later".
SERVER_BUSY_CLOSE_CODE = 1013


class ServerBusy(Exception):
    """No hubo cupo dentro del tiempo de espera."""


class AnalysisCapacity:
    def __init__(self, settings: ServerLoadSettings | None = None) -> None:
        self.settings = settings or ServerLoadSettings()
        self._sessions = asyncio.Semaphore(self.settings.max_active_sessions)
        self._analyses = asyncio.Semaphore(self.settings.max_concurrent_analyses)
        self._executor = ThreadPoolExecutor(max_workers=self.settings.max_concurrent_analyses,
                                            thread_name_prefix="emotv-analysis")

    async def _acquire(self, semaphore: asyncio.Semaphore) -> None:
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=self.settings.busy_wait_seconds)
        except asyncio.TimeoutError as error:
            raise ServerBusy(SERVER_BUSY_MESSAGE) from error

    async def acquire_session(self) -> None:
        """Toma un cupo de sesión activa; se libera con release_session al cerrar."""
        await self._acquire(self._sessions)

    def release_session(self) -> None:
        self._sessions.release()

    @asynccontextmanager
    async def session(self):
        """Cupo de sesión activa durante un bloque."""
        await self.acquire_session()
        try:
            yield
        finally:
            self.release_session()

    async def run(self, function: Callable[..., T], *args) -> T:
        """Ejecuta un análisis en el pool propio, dentro del límite de simultáneos."""
        await self._acquire(self._analyses)
        return await self._start(function, *args)

    async def try_run(self, function: Callable[..., T], *args) -> tuple[bool, T | None]:
        """Como run, pero sin esperar: sin cupo libre devuelve (False, None) y el
        análisis no se hace (un cuadro de práctica se descarta)."""
        if self._analyses.locked():
            return False, None
        await self._analyses.acquire()  # hay cupo: no espera
        return True, await self._start(function, *args)

    async def _start(self, function: Callable[..., T], *args) -> T:
        try:
            future = asyncio.get_running_loop().run_in_executor(self._executor, function, *args)
        except BaseException:
            self._analyses.release()
            raise
        # El cupo se libera cuando el hilo termina, aunque la conexión se cierre
        # antes: un análisis en curso sigue contando hasta acabar.
        future.add_done_callback(lambda _: self._analyses.release())
        return await asyncio.shield(future)
