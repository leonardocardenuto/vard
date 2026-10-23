from queue import Queue
from unittest.mock import MagicMock

import numpy as np
import pytest

from fall_detection.person_crop import PersonWindowCropper, crop_window
from api.services.native_preview import NativePreview, _publish_crop, _preview_process


def test_union_keeps_whole_fall_and_same_transform_through_time():
    frames = [np.full((100, 200, 3), value, np.uint8) for value in (50, 100, 150)]
    result, box = crop_window(frames, [(80, 10, 100, 90), (90, 70, 180, 95)], margin=0, size=100)
    assert box == (80, 10, 180, 95)
    assert len(result) == 3
    for output, value in zip(result, (50, 100, 150)):
        assert output.shape == (100, 100, 3)
        assert np.all(output[7:92] == value)
        assert np.all(output[:7] == 0)
    assert np.all(frames[0] == 50)


def test_margin_clips_to_frame_and_ignores_invalid_boxes():
    frames = [np.ones((100, 200, 3), np.uint8)]
    _, box = crop_window(frames, [(0, 0, 200, 100), (3, 5, 1, 2), (0, 0, float('nan'), 5)])
    assert box == (0, 0, 200, 100)
    result, box = crop_window(frames, [])
    assert result is frames
    assert box is None


def test_missing_model_never_downloads(tmp_path):
    cropper = PersonWindowCropper(str(tmp_path / 'missing.pt'))
    with pytest.raises(FileNotFoundError, match='person-crop-model'):
        cropper.apply([np.zeros((40, 60, 3), np.uint8)])


def test_yolo_gets_bgr_and_all_frames_contribute(tmp_path):
    from types import SimpleNamespace
    cropper = PersonWindowCropper(str(tmp_path / 'model.pt'))
    cropper._model = MagicMock()
    cropper._model.predict.return_value = [SimpleNamespace(boxes=SimpleNamespace(
        xyxy=SimpleNamespace(cpu=lambda: SimpleNamespace(numpy=lambda: np.array([[2, 3, 10, 20]]))))) ]
    frames = [np.full((30, 40, 3), [255, 0, 0], np.uint8) for _ in range(2)]
    result, box = cropper.apply(frames)
    assert len(result) == 2 and box is not None
    assert cropper._model.predict.call_count == 2
    assert cropper._model.predict.call_args.args[0][0, 0].tolist() == [0, 0, 255]


def test_gui_control_reads_latest_state():
    preview = NativePreview.__new__(NativePreview)
    preview._controls = Queue(maxsize=4)
    for value in (0, 1, 0, 1, 0, 1):
        _publish_crop(preview._controls, value)
    assert preview.poll_crop_enabled() is True
    assert preview.poll_crop_enabled() is None


def test_mixed_frame_sizes_are_rejected():
    with pytest.raises(ValueError, match='dimensao'):
        crop_window([np.zeros((10, 20, 3)), np.zeros((20, 10, 3))], [(0, 0, 10, 10)])


def test_preview_toggle_sends_control_back_to_monitor(monkeypatch):
    import cv2
    frames, controls = Queue(), Queue()
    frames.put(None)
    for name in ('namedWindow', 'resizeWindow', 'destroyAllWindows'):
        monkeypatch.setattr(cv2, name, MagicMock())
    monkeypatch.setattr(cv2, 'waitKey', lambda _: ord('q'))
    trackbar = MagicMock(side_effect=lambda _name, _window, initial, _max, callback: (callback(initial), callback(1)))
    monkeypatch.setattr(cv2, 'createTrackbar', trackbar)
    _preview_process(frames, 'VARD test', controls)
    assert trackbar.call_args.args[:4] == ('Recorte pessoa', 'VARD test', 0, 1)
    assert controls.get_nowait() is False
    assert controls.get_nowait() is True
