from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationRule:
    severity: str
    channels: tuple[str, ...]


NOTIFICATION_RULES = {
    "CRITICAL": NotificationRule(
        severity="CRITICAL",
        channels=("CONSOLE",),
    ),
    "HIGH": NotificationRule(
        severity="HIGH",
        channels=("CONSOLE",),
    ),
    "MEDIUM": NotificationRule(
        severity="MEDIUM",
        channels=(),
    ),
    "LOW": NotificationRule(
        severity="LOW",
        channels=(),
    ),
}


def get_notification_channels(
    severity: str,
) -> tuple[str, ...]:

    normalized_severity = severity.upper()

    rule = NOTIFICATION_RULES.get(
        normalized_severity
    )

    if rule is None:
        return ()

    return rule.channels
