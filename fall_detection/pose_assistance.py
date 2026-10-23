"""Experimental temporal pose evidence, not a trained fall probability."""
from __future__ import annotations

import math
import numpy as np


def assess_pose(poses, sample_fps):
    result = {"reliable": False, "reason": "pontos insuficientes", "coverage": 0.0,
              "evidence": None, "hip_drop": None, "hip_speed": None,
              "trunk_change_degrees": None, "low_posture_fraction": None}
    if not math.isfinite(sample_fps) or sample_fps <= 0:
        return result
    samples = []
    for index, pose in enumerate(poses):
        if pose is None:
            continue
        points = np.asarray(pose, dtype=float)
        if points.shape != (17, 3):
            continue
        torso = points[[5, 6, 11, 12]]
        if not np.isfinite(torso).all() or np.min(torso[:, 2]) < 0.5:
            continue
        shoulder, hip = torso[:2, :2].mean(axis=0), torso[2:, :2].mean(axis=0)
        length = np.linalg.norm(hip - shoulder)
        if length < 5:
            continue
        samples.append((index, hip, hip - shoulder, length))
    result["coverage"] = len(samples) / max(1, len(poses))
    if len(samples) < 4 or result["coverage"] < 0.75:
        return result
    indices = np.array([s[0] for s in samples])
    if np.max(np.diff(indices)) > 2 or (indices[-1] - indices[0]) / sample_fps < 0.5:
        result["reason"] = "sequencia curta ou interrompida"
        return result
    hips = np.array([s[1] for s in samples])
    trunks = np.array([s[2] for s in samples])
    lengths = np.array([s[3] for s in samples])
    if lengths.max() / lengths.min() > 2.5:
        result["reason"] = "escala ou identidade instavel"
        return result
    scale = float(np.median(lengths))
    initial_count = max(1, len(samples) // 4)
    initial_trunk = np.median(trunks[:initial_count], axis=0)
    norm = float(np.linalg.norm(initial_trunk))
    if norm < 5:
        return result
    down = initial_trunk / norm
    # Project relative to the initial trunk, rather than the image's vertical.
    origin = np.median(hips[:initial_count], axis=0)
    displacement = ((hips - origin) @ down) / scale
    speed = np.diff(displacement) / (np.diff(indices) / sample_fps)
    cosine = np.clip((trunks @ down) / lengths, -1, 1)
    angles = np.degrees(np.arccos(cosine))
    tail = max(2, len(samples) // 3)
    drop = max(0.0, float(np.median(displacement[-tail:])))
    peak_speed = max(0.0, float(np.max(speed)))
    change = float(np.median(angles[-tail:]))
    low_fraction = float(np.mean((displacement[-tail:] >= 0.5) & (angles[-tail:] >= 35)))
    # All three cues must agree; sitting with an upright trunk has low evidence.
    evidence = min(1.0, drop / 0.8) * min(1.0, peak_speed / 1.5) * min(1.0, change / 60)
    evidence *= 0.5 + 0.5 * low_fraction
    result.update(reliable=True, reason="ok", evidence=float(evidence), hip_drop=drop,
                  hip_speed=peak_speed, trunk_change_degrees=change, low_posture_fraction=low_fraction)
    return result


def assist_jepa(probability, pose, *, threshold, mode="observe", weight=0.1):
    if mode not in {"off", "observe", "assist"} or not math.isfinite(weight) or not 0 <= weight <= 0.1:
        raise ValueError("Modo de pose ou peso invalido (maximo 0.10).")
    adjusted = probability
    # Never override confident JEPA predictions or make a pose-only decision.
    if (mode == "assist" and pose.get("reliable") and pose.get("evidence") is not None
            and 0.5 <= probability < 0.95 and abs(probability - threshold) <= 0.15):
        adjusted = float(np.clip(probability + weight * (2 * pose["evidence"] - 1), 0, 1))
    return {"mode": mode, "weight": weight, "jepa_probability": probability,
            "decision_score": adjusted, "adjustment": adjusted - probability, **pose}
