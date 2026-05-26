from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, Iterable, List

import numpy as np


@dataclass(frozen=True)
class BufferedFrame:
    frame: np.ndarray
    timestamp: float


class FrameBuffer:
    def __init__(self, max_frames: int):
        if max_frames <= 0:
            raise ValueError("max_frames deve ser maior que zero.")
        self._frames: Deque[BufferedFrame] = deque(maxlen=max_frames)
        self._lock = Lock()

    def append(self, frame: np.ndarray, timestamp: float):
        with self._lock:
            self._frames.append(BufferedFrame(frame=frame, timestamp=timestamp))

    def __len__(self) -> int:
        with self._lock:
            return len(self._frames)

    def clear(self):
        with self._lock:
            self._frames.clear()

    def frames(self) -> List[BufferedFrame]:
        with self._lock:
            return list(self._frames)

    def latest_timestamp(self) -> float | None:
        with self._lock:
            if not self._frames:
                return None
            return self._frames[-1].timestamp

    def sample_window(
        self,
        num_frames: int,
        sample_fps: float,
        end_timestamp: float | None = None,
    ) -> List[np.ndarray]:
        buffered_window = self.sample_window_buffered(
            num_frames=num_frames,
            sample_fps=sample_fps,
            end_timestamp=end_timestamp,
        )
        return [item.frame for item in buffered_window]

    def sample_window_buffered(
        self,
        num_frames: int,
        sample_fps: float,
        end_timestamp: float | None = None,
    ) -> List[BufferedFrame]:
        if num_frames <= 0:
            raise ValueError("num_frames deve ser maior que zero.")
        if sample_fps <= 0:
            raise ValueError("sample_fps deve ser maior que zero.")
        with self._lock:
            if not self._frames:
                return []
            frames = list(self._frames)
        end_ts = frames[-1].timestamp if end_timestamp is None else end_timestamp
        window_seconds = (num_frames - 1) / sample_fps
        start_ts = end_ts - window_seconds

        available = [item for item in frames if item.timestamp <= end_ts]
        if not available:
            return []
        if available[0].timestamp > start_ts or available[-1].timestamp < end_ts:
            return []

        candidates = [item for item in available if start_ts <= item.timestamp <= end_ts]
        if not candidates:
            return []

        return self._sample_evenly_buffered(candidates, num_frames)

    @staticmethod
    def _sample_evenly(frames: Iterable[BufferedFrame], num_frames: int) -> List[np.ndarray]:
        return [item.frame for item in FrameBuffer._sample_evenly_buffered(frames, num_frames)]

    @staticmethod
    def _sample_evenly_buffered(frames: Iterable[BufferedFrame], num_frames: int) -> List[BufferedFrame]:
        frame_list = list(frames)
        if not frame_list:
            return []
        if len(frame_list) == 1:
            return [frame_list[0]] * num_frames

        indices = np.linspace(0, len(frame_list) - 1, num_frames).astype(int).tolist()
        sampled = [frame_list[index] for index in indices]
        while len(sampled) < num_frames:
            sampled.append(sampled[-1])
        return sampled[:num_frames]
