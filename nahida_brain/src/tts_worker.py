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
            self.interrupt()
            self._clear_pending()

        self._queue.put(text)

    def interrupt(self):
        current_stop = self._current_stop

        if current_stop is not None:
            current_stop.set()

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

            stop_event = threading.Event()
            self._current_stop = stop_event

            try:
                print("[TTS] Speaking in background...")

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

    def shutdown(
        self,
        wait=False,
    ):
        self._shutdown.set()
        self.interrupt()
        self._clear_pending()

        if wait:
            self._thread.join(
                timeout=2.0,
            )
