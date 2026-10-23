import numpy as np
import pytest

from fall_detection.pose_assistance import assess_pose, assist_jepa


def sequence(*, fall=True, angle=0):
    frames = []
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    for index in range(16):
        progress = np.clip((index - 3) / 6, 0, 1)
        hip = np.array([100, 80 + 70 * progress])
        theta = progress * np.pi / 2 if fall else 0
        trunk = np.array([40 * np.sin(theta), 40 * np.cos(theta)])
        shoulder = hip - trunk
        points = np.zeros((17, 3))
        for joint, center, dx in ((5, shoulder, -5), (6, shoulder, 5), (11, hip, -5), (12, hip, 5)):
            points[joint] = [*(rotation @ (center + [dx, 0])), 0.9]
        frames.append(points.tolist())
    return frames


def test_pose_requires_descent_rotation_and_low_posture_together():
    falling = assess_pose(sequence(), 6)
    sitting = assess_pose(sequence(fall=False), 6)
    assert falling['reliable'] and sitting['reliable']
    assert falling['evidence'] > 0.9
    assert sitting['evidence'] == 0
    assert falling['trunk_change_degrees'] > 80
    assert falling['hip_drop'] > 1


def test_features_are_invariant_to_camera_roll_and_uniform_scale():
    reference = assess_pose(sequence(), 6)
    rotated = assess_pose(sequence(angle=0.7), 6)
    scaled = np.array(sequence())
    scaled[:, :, :2] *= 2
    for candidate in (rotated, assess_pose(scaled.tolist(), 6)):
        for key in ('hip_drop', 'hip_speed', 'trunk_change_degrees', 'evidence'):
            assert candidate[key] == pytest.approx(reference[key])


@pytest.mark.parametrize('poses', [[], [None] * 16, sequence()[:3]])
def test_missing_or_short_pose_is_unreliable(poses):
    assert not assess_pose(poses, 6)['reliable']


def test_low_confidence_and_large_gaps_do_not_adjust_jepa():
    poses = sequence()
    for frame in poses:
        frame[11][2] = 0.1
    result = assess_pose(poses, 6)
    assert not result['reliable']
    assert assist_jepa(0.82, result, threshold=0.85, mode='assist')['decision_score'] == 0.82
    poses = sequence()
    poses[5:8] = [None] * 3
    assert not assess_pose(poses, 6)['reliable']


def test_observe_keeps_jepa_and_assist_is_bounded():
    evidence = assess_pose(sequence(), 6)
    assert assist_jepa(0.82, evidence, threshold=0.85, mode='observe')['decision_score'] == 0.82
    assisted = assist_jepa(0.82, evidence, threshold=0.85, mode='assist', weight=0.07)
    assert assisted['decision_score'] == pytest.approx(0.89)
    assert assisted['jepa_probability'] == 0.82
    negative = assist_jepa(0.87, assess_pose(sequence(fall=False), 6), threshold=0.85, mode='assist')
    assert negative['decision_score'] == pytest.approx(0.77)


@pytest.mark.parametrize('probability', [0.2, 0.49, 0.6, 0.95, 0.99, 1.0])
def test_pose_alone_never_creates_alert_or_overrides_strong_jepa(probability):
    result = assist_jepa(probability, assess_pose(sequence(), 6), threshold=0.85, mode='assist')
    assert result['decision_score'] == probability


def test_invalid_weight_is_rejected():
    for weight in (-0.1, 0.2, float('nan')):
        with pytest.raises(ValueError):
            assist_jepa(0.8, {}, threshold=0.85, mode='assist', weight=weight)
