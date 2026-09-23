import asyncio
import threading

class AsyncRuntime:
    def __init__(self):
        self.loop = asyncio.new_event_loop()

        self.thread = threading.Thread(
            target=self._run_event_loop,
            daemon=True,
        )
        self.thread.start()

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro, callback):
        future = asyncio.run_coroutine_threadsafe(
            coro,
            self.loop,
        )

        def done_callback(future):
            try:
                result = future.result()
            except Exception as exc:
                result = exc

            callback(result)

        future.add_done_callback(done_callback)


    def stop(self):
        self.loop.call_soon_threadsafe(
            self.loop.stop,
        )

        if self.thread.is_alive():
            self.thread.join(timeout=2)