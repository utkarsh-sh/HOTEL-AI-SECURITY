from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Iterable


@dataclass(frozen=True)
class LatencySample:
    event_type: str
    frame_to_ai_ms: float
    ai_to_persistence_ms: float
    persistence_to_notification_ms: float
    end_to_end_ms: float


@dataclass(frozen=True)
class LatencyMetrics:
    count: int
    mean_ms: float | None
    median_ms: float | None
    p95_ms: float | None
    max_ms: float | None

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "count": self.count,
            "mean_ms": self.mean_ms,
            "median_ms": self.median_ms,
            "p95_ms": self.p95_ms,
            "max_ms": self.max_ms,
        }


def percentile(values: Iterable[float], percentile_value: float) -> float | None:
    values = sorted(float(value) for value in values)

    if not values:
        return None

    if not 0 <= percentile_value <= 100:
        raise ValueError("percentile_value must be between 0 and 100.")

    if len(values) == 1:
        return values[0]

    rank = (len(values) - 1) * (percentile_value / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    fraction = rank - lower

    return values[lower] + (
        values[upper] - values[lower]
    ) * fraction


def calculate_latency_metrics(
    samples: Iterable[LatencySample],
) -> LatencyMetrics:
    values = [
        sample.end_to_end_ms
        for sample in samples
    ]

    if not values:
        return LatencyMetrics(
            count=0,
            mean_ms=None,
            median_ms=None,
            p95_ms=None,
            max_ms=None,
        )

    return LatencyMetrics(
        count=len(values),
        mean_ms=mean(values),
        median_ms=median(values),
        p95_ms=percentile(values, 95),
        max_ms=max(values),
    )


class LatencyMeasurement:
    """Collect real event-path latency samples without changing event behavior."""

    def __init__(self) -> None:
        self.samples: list[LatencySample] = []

    def record(
        self,
        *,
        event_type: str,
        frame_received_at: float,
        ai_completed_at: float,
        persisted_at: float,
        notification_queued_at: float,
    ) -> LatencySample:
        sample = LatencySample(
            event_type=event_type,
            frame_to_ai_ms=(
                ai_completed_at - frame_received_at
            ) * 1000.0,
            ai_to_persistence_ms=(
                persisted_at - ai_completed_at
            ) * 1000.0,
            persistence_to_notification_ms=(
                notification_queued_at - persisted_at
            ) * 1000.0,
            end_to_end_ms=(
                notification_queued_at - frame_received_at
            ) * 1000.0,
        )

        self.samples.append(sample)
        return sample

    def metrics_by_event_type(self) -> dict[str, LatencyMetrics]:
        event_types = sorted(
            {sample.event_type for sample in self.samples}
        )

        return {
            event_type: calculate_latency_metrics(
                sample
                for sample in self.samples
                if sample.event_type == event_type
            )
            for event_type in event_types
        }

    def overall_metrics(self) -> LatencyMetrics:
        return calculate_latency_metrics(self.samples)

    def to_dict(self) -> dict[str, object]:
        return {
            "overall": self.overall_metrics().to_dict(),
            "by_event_type": {
                event_type: metrics.to_dict()
                for event_type, metrics
                in self.metrics_by_event_type().items()
            },
        }
