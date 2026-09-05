import queue
import threading


class TTSWorker:
    def __init__(
        self,
        client,
    ):
        self.client = client
        self._queue = queue.Queue()
        self._shutdown = threading.Event()
        self._current_stop = None
        self._idle_event = threading.Event()
        self._idle_event.set()

        self._thread = threading.Thread(
            target=self._run,
            name="NahidaTTSWorker",
            daemon=True,
        )

        self._thread.start()

    def submit(
        self,
        text,
        interrupt=False,
    ):
        if not text:
            return

        if interrupt:
            self.cancel_all()

        self._idle_event.clear()
        self._queue.put(text)

    def interrupt(self):
        current_stop = self._current_stop

        if current_stop is not None:
            current_stop.set()

    def clear_pending(self):
        self._clear_pending()

    def cancel_all(self):
        self.interrupt()
        self._clear_pending()

        if self._current_stop is None:
            self._idle_event.set()

    def wait_until_idle(
        self,
        timeout=None,
    ):
        return self._idle_event.wait(
            timeout=timeout,
        )

    def cancel_and_wait(
        self,
        timeout=3.0,
    ):
        self.cancel_all()

        return self.wait_until_idle(
            timeout=timeout,
        )

    def _clear_pending(self):
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    def _run(self):
        while not self._shutdown.is_set():
            try:
                text = self._queue.get(
                    timeout=0.1,
                )
            except queue.Empty:
                continue

            self._idle_event.clear()

            stop_event = threading.Event()
            self._current_stop = stop_event

            try:
                print(
                    "[TTS] Speaking in background..."
                )

                self.client.speak(
                    text,
                    stop_event=stop_event,
                )

            except Exception as exc:
                print(
                    f"[TTS] Failed: {exc}"
                )

            finally:
                self._current_stop = None
                self._queue.task_done()

                if self._queue.empty():
                    self._idle_event.set()

    def shutdown(
        self,
        wait=False,
    ):
        self._shutdown.set()
        self.cancel_all()

        if wait:
            self._thread.join(
                timeout=2.0,
            )
