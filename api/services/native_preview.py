from __future__ import annotations

"""A small, dedicated process for the OpenCV monitor window.

macOS requires HighGUI/AppKit calls to run on a process' main thread. The
monitor itself runs in a background thread under Uvicorn, so calling
``cv2.imshow`` there triggers an opaque OpenCV C++ exception. Keeping the
window in this child process leaves capture and inference uninterrupted.
"""

import multiprocessing as mp
from queue import Empty, Full

import cv2
import numpy as np


def _publish_crop(control_queue, value):
    try:
        control_queue.put_nowait(bool(value))
    except Full:
        try:
            control_queue.get_nowait()
        except Empty:
            pass
        try:
            control_queue.put_nowait(bool(value))
        except Full:
            pass


def _preview_process(frame_queue, window_name: str, control_queue=None, crop_enabled=False) -> None:
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 540)
    if control_queue is not None:
        cv2.createTrackbar("Recorte pessoa", window_name, int(crop_enabled), 1,
                          lambda value: _publish_crop(control_queue, value))
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

    def __init__(self, camera_name: str, *, crop_control: bool = False, crop_enabled=False):
        context = mp.get_context("spawn")
        self._queue = context.Queue(maxsize=1)
        self._controls = context.Queue(maxsize=4) if crop_control else None
        self._process = context.Process(
            target=_preview_process,
            args=(self._queue, f"VARD Fall Monitor - {camera_name}", self._controls, crop_enabled),
            name="vard-fall-preview",
            daemon=True,
        )
        self._process.start()

    @property
    def is_alive(self) -> bool:
        return self._process.is_alive()

    def submit(self, frame_bgr) -> None:
        if not self.is_alive:
            return
        success, encoded = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success:
            return
        try:
            self._queue.put_nowait(encoded.tobytes())
        except Full:
            # The window displays the most recent frame it received; never
            # slow inference to render an old preview frame.
            return

    def poll_crop_enabled(self) -> bool | None:
        latest = None
        if self._controls is not None:
            while True:
                try:
                    latest = self._controls.get_nowait()
                except Empty:
                    break
        return latest

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
        if self._controls is not None:
            self._controls.close()
