from django.conf import settings

from . import health


def health_alert(request):
    """For superusers on monitored servers: a warning when the health samples stop or
    memory, swap or disk reach the critical level."""
    user = getattr(request, "user", None)
    if user is None or not user.is_superuser or not settings.HEALTH_MONITORED:
        return {}
    latest = health.latest()
    if latest is None:
        return {"health_alert": {"no_samples": True}}
    if health.stopped(latest):
        return {"health_alert": {"stopped": latest["time"]}}
    # Not the processor: a busy moment is normal, and it does not break anything by itself.
    critical = [
        key for key, level in health.levels(latest).items() if level == "critical" and key != "cpu"
    ]
    return {"health_alert": {"critical": critical}} if critical else {}
