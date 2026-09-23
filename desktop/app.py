import asyncio
import logging
import tkinter as tk
from queue import Empty, Queue
from tkinter import ttk

from desktop.fl_view import FLView
from desktop.hh_view import HHView


log = logging.getLogger(__name__)


class App(tk.Tk):
    def __init__(
        self,
        *,
        fl_backend,
        hh_backend,
        runtime,
    ) -> None:
        super().__init__()

        self.title("Job Watcher")
        self.geometry("1450x800")

        self.fl_backend = fl_backend
        self.hh_backend = hh_backend
        self.runtime = runtime

        self.callback_queue = Queue()
        self.is_closing = False

        self._create_widgets()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

        self.after(
            50,
            self.process_callbacks,
        )

    def _create_widgets(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(
            fill="both",
            expand=True,
        )

        self.fl_view = FLView(
            parent=notebook,
            backend=self.fl_backend,
            enqueue_callback=self.enqueue_callback,
        )

        self.hh_view = HHView(
            parent=notebook,
            backend=self.hh_backend,
            enqueue_callback=self.enqueue_callback,
        )

        notebook.add(
            self.fl_view,
            text="FL.ru",
        )

        notebook.add(
            self.hh_view,
            text="HH.ru",
        )

    def enqueue_callback(
        self,
        callback,
        *args,
        **kwargs,
    ) -> None:
        self.callback_queue.put(
            (callback, args, kwargs),
        )

    def process_callbacks(self) -> None:
        try:
            while True:
                callback, args, kwargs = (
                    self.callback_queue.get_nowait()
                )

                callback(*args, **kwargs)

        except Empty:
            pass

        if not self.is_closing:
            self.after(
                50,
                self.process_callbacks,
            )

    def on_close(self) -> None:
        if self.is_closing:
            return

        self.is_closing = True

        async def shutdown():
            return await asyncio.gather(
                self.fl_backend.close(),
                self.hh_backend.close(),
                return_exceptions=True,
            )

        self.runtime.submit(
            shutdown(),
            self._on_backends_closed,
        )

    def _on_backends_closed(self, result) -> None:
        # Этот callback вызывается из runtime-thread,
        # поэтому Tkinter здесь напрямую не трогаем.
        self.after(
            0,
            self._finish_close,
            result,
        )

    def _finish_close(self, result) -> None:
        if isinstance(result, Exception):
            log.error(
                "Ошибка при закрытии backend: %s",
                result,
                exc_info=result,
            )

        elif isinstance(result, list):
            for error in result:
                if isinstance(error, Exception):
                    log.error(
                        "Ошибка при закрытии ресурса: %s",
                        error,
                        exc_info=error,
                    )

        self.runtime.stop()
        self.destroy()