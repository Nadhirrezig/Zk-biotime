"""Run blocking work (DB queries, engine) off the UI thread."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from zkreport.service import friendly_error


class _Job(QObject):
    done = pyqtSignal(int, object)
    error = pyqtSignal(int, str)

    def __init__(self, job_id: int, fn: Callable[[], object]):
        super().__init__()
        self._job_id = job_id
        self._fn = fn

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # reported to the UI, never raised in the thread
            self.error.emit(self._job_id, friendly_error(exc))
        else:
            self.done.emit(self._job_id, result)


class JobRunner(QObject):
    """Starts each job in its own QThread and relays results to the UI thread.

    Results are tagged with the job id so callers can drop stale answers."""

    done = pyqtSignal(int, object)
    error = pyqtSignal(int, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._next_id = 0
        self._running: dict[int, tuple[QThread, _Job]] = {}

    def start(self, fn: Callable[[], object]) -> int:
        self._next_id += 1
        job_id = self._next_id
        thread = QThread()
        job = _Job(job_id, fn)
        job.moveToThread(thread)
        thread.started.connect(job.run)
        job.done.connect(self._on_done)
        job.error.connect(self._on_error)
        self._running[job_id] = (thread, job)
        thread.start()
        return job_id

    def is_running(self, job_id: int | None) -> bool:
        return job_id in self._running

    def wait_all(self, msecs: int = 5000) -> None:
        for thread, _ in list(self._running.values()):
            thread.quit()
            thread.wait(msecs)

    @pyqtSlot(int, object)
    def _on_done(self, job_id: int, result: object) -> None:
        self._finish(job_id)
        self.done.emit(job_id, result)

    @pyqtSlot(int, str)
    def _on_error(self, job_id: int, message: str) -> None:
        self._finish(job_id)
        self.error.emit(job_id, message)

    def _finish(self, job_id: int) -> None:
        # Runs in the UI thread (queued from the job); the job's run() has returned.
        entry = self._running.pop(job_id, None)
        if entry:
            thread, job = entry
            thread.quit()
            thread.wait()
            job.deleteLater()
            thread.deleteLater()
