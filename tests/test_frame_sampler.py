import pytest

from video.frame_sampler import FrameSampler


def test_invalid_source_fps():
    with pytest.raises(ValueError):
        FrameSampler(0, 5)


def test_invalid_target_fps():
    with pytest.raises(ValueError):
        FrameSampler(25, 0)


def test_target_fps_is_capped_by_source_fps():
    sampler = FrameSampler(5, 10)

    assert sampler.target_fps == 5


def test_sampling_5_fps_from_25_fps():
    sampler = FrameSampler(25, 5)

    processed = []

    for _ in range(25):
        processed.append(
            sampler.should_process()
        )

    assert sum(processed) == 5
    assert sampler.sampled_frames == 5


def test_sampling_2_fps_from_25_fps():
    sampler = FrameSampler(25, 2)

    processed = []

    for _ in range(25):
        processed.append(
            sampler.should_process()
        )

    assert sum(processed) == 2
    assert sampler.sampled_frames == 2


def test_sampling_does_not_exceed_source_rate():
    sampler = FrameSampler(5, 5)

    processed = [
        sampler.should_process()
        for _ in range(5)
    ]

    assert sum(processed) == 5


def test_reset():
    sampler = FrameSampler(25, 5)

    for _ in range(25):
        sampler.should_process()

    sampler.reset()

    assert sampler.frame_index == 0
    assert sampler.sampled_frames == 0
    assert sampler.next_sample_frame == 0.0

    assert sampler.should_process() is True
