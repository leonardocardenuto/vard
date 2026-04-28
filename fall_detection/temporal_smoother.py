from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque


@dataclass(frozen=True)
class SmoothingResult:
    alert: bool
    moving_average: float
    consecutive_hits: int


class TemporalSmoother:
    def __init__(self, threshold: float, window_size: int, min_consecutive_hits: int = 2):
        if not 0 <= threshold <= 1:
            raise ValueError("threshold deve estar entre 0 e 1.")
        if window_size <= 0:
            raise ValueError("window_size deve ser maior que zero.")
        if min_consecutive_hits <= 0:
            raise ValueError("min_consecutive_hits deve ser maior que zero.")

        self.threshold = threshold
        self.min_consecutive_hits = min_consecutive_hits
        self._values: Deque[float] = deque(maxlen=window_size)
        self._consecutive_hits = 0

    def update(self, fall_probability: float) -> SmoothingResult:
        probability = max(0.0, min(1.0, float(fall_probability)))
        self._values.append(probability)

        if probability >= self.threshold:
            self._consecutive_hits += 1
        else:
            self._consecutive_hits = 0

        moving_average = sum(self._values) / len(self._values)
        alert = (
            self._consecutive_hits >= self.min_consecutive_hits
            or (len(self._values) == self._values.maxlen and moving_average >= self.threshold)
        )
        return SmoothingResult(
            alert=alert,
            moving_average=moving_average,
            consecutive_hits=self._consecutive_hits,
        )

    def reset(self):
        self._values.clear()
        self._consecutive_hits = 0
