"""Ponte generica entre corrotinas assincronas (nostr-sdk) e o event loop do PyQt6:
roda uma corrotina numa QThread dedicada e devolve o resultado via sinais, no mesmo
padrao dos demais workers (FlowerClientWorker/FlowerServerWorker)."""
import asyncio
from typing import Callable, Coroutine

from PyQt6.QtCore import QThread, pyqtSignal


class AsyncTask(QThread):
    """Executa `coro_factory()` num loop asyncio proprio, sem bloquear a GUI."""

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, coro_factory: Callable[[], Coroutine], parent=None):
        super().__init__(parent)
        self._coro_factory = coro_factory

    def run(self):
        try:
            result = asyncio.run(self._coro_factory())
        except Exception as exc:  # encaminha qualquer falha para a GUI sem derruba-la
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
