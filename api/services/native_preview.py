from __future__ import annotations

"""A small, dedicated process for the OpenCV monitor window.

macOS requires HighGUI/AppKit calls to run on a process' main thread. The
monitor itself runs in a background thread under Uvicorn, so calling
``cv2.imshow`` there triggers an opaque OpenCV C++ exception. Keeping the
window in this child process leaves capture and inference uninterrupted.
"""

import multiprocessing as mp
import time
from queue import Empty, Full

import cv2
import numpy as np


def _preview_process(frame_queue, window_name: str) -> None:
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 540)
    try:
        while True:
            try:
                encoded = frame_queue.get(timeout=0.03)
            except Empty:
                encoded = None

            if encoded is False:
                return
            if encoded is not None:
                frame = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                return
    except KeyboardInterrupt:
        # The monitor is normally stopped together with its foreground server.
        return
    finally:
        cv2.destroyAllWindows()


class NativePreview:
    """Non-blocking frame sender for the separate desktop preview window."""

    def __init__(self, camera_name: str, *, max_fps: float = 8.0, max_width: int = 960):
        if max_fps <= 0 or max_width < 1:
            raise ValueError('FPS e largura do preview devem ser positivos.')
        self._interval = 1 / max_fps
        self._max_width = max_width
        self._last_submission = -float('inf')
        context = mp.get_context("spawn")
        self._queue = context.Queue(maxsize=1)
        self._process = context.Process(
            target=_preview_process,
            args=(self._queue, f"VARD Fall Monitor - {camera_name}"),
            name="vard-fall-preview",
            daemon=True,
        )
        self._process.start()

    @property
    def is_alive(self) -> bool:
        return self._process.is_alive()

    def should_submit(self) -> bool:
        return self.is_alive and time.monotonic() - self._last_submission >= self._interval

    def prepare_frame(self, frame):
        height, width = frame.shape[:2]
        if width <= self._max_width:
            return frame
        return cv2.resize(frame, (self._max_width, max(1, round(height * self._max_width / width))),
                          interpolation=cv2.INTER_AREA)

    def submit(self, frame_bgr) -> bool:
        if not self.should_submit():
            return False
        self._last_submission = time.monotonic()
        success, encoded = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if not success:
            return False
        try:
            self._queue.put_nowait(encoded.tobytes())
        except Full:
            # Replace the stale image instead of accumulating display latency.
            try:
                self._queue.get_nowait()
            except Empty:
                pass
            try:
                self._queue.put_nowait(encoded.tobytes())
            except Full:
                return False
        return True

    def close(self) -> None:
        if self.is_alive:
            try:
                self._queue.put_nowait(False)
            except Full:
                pass
            self._process.join(timeout=2)
        if self.is_alive:
            self._process.terminate()
            self._process.join(timeout=2)
        self._queue.close()
