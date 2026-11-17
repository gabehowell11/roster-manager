"""Run slow work (like downloads) off the UI thread so the window never freezes."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(object)


class _Task(QRunnable):
    def __init__(self, work: Callable[[], Any], signals: _Signals) -> None:
        super().__init__()
        self.work = work
        self.signals = signals

    def run(self) -> None:
        try:
            result = self.work()
        except Exception as error:  # noqa: BLE001 - any failure must reach on_error, not kill the thread
            self.signals.failed.emit(error)
        else:
            self.signals.finished.emit(result)


class BackgroundRunner:
    """Runs a function on Qt's thread pool and calls back on the UI thread."""

    def __init__(self, pool: QThreadPool | None = None) -> None:
        self.pool = pool if pool is not None else QThreadPool.globalInstance()
        self._active: set[_Signals] = set()  # keeps signal objects alive until done

    def run(
        self,
        work: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        signals = _Signals()
        self._active.add(signals)

        def finish(result: object) -> None:
            self._active.discard(signals)
            on_done(result)

        def fail(error: object) -> None:
            self._active.discard(signals)
            on_error(error if isinstance(error, Exception) else RuntimeError(str(error)))

        signals.finished.connect(finish)
        signals.failed.connect(fail)
        self.pool.start(_Task(work, signals))

    @property
    def busy(self) -> bool:
        return bool(self._active)
