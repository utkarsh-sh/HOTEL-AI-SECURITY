class FrameSampler:
    """Select frames from a source according to a target FPS."""

    def __init__(
        self,
        source_fps: float,
        target_fps: float,
    ):
        if source_fps <= 0:
            raise ValueError(
                "source_fps must be greater than 0."
            )

        if target_fps <= 0:
            raise ValueError(
                "target_fps must be greater than 0."
            )

        self.source_fps = source_fps
        self.target_fps = min(
            target_fps,
            source_fps,
        )

        self.frame_index = 0
        self.sampled_frames = 0

        self.interval = (
            self.source_fps / self.target_fps
        )

        self.next_sample_frame = 0.0

    def should_process(self) -> bool:
        """Return True when the current frame should reach AI."""
        current_index = self.frame_index

        should_process = (
            current_index >= self.next_sample_frame
        )

        self.frame_index += 1

        if should_process:
            self.sampled_frames += 1
            self.next_sample_frame += self.interval

        return should_process

    def reset(self) -> None:
        """Reset sampling state."""
        self.frame_index = 0
        self.sampled_frames = 0
        self.next_sample_frame = 0.0
