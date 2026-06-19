from django.core.management.base import BaseCommand
from django.utils import timezone

_DIVIDER = "─" * 30


class Command(BaseCommand):
    help = "Take a HealthSnapshot for every active service and print a summary."

    def handle(self, *args, **options):
        from nocturne.detection import compute_health_score, take_health_snapshot
        from nocturne.models import HealthSnapshot, LogEntry

        # Determine which services are active (logged in last 1 hour)
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=1)
        services = list(
            LogEntry.objects.filter(timestamp__gte=since)
            .order_by()
            .values_list("service_name", flat=True)
            .distinct()
        )

        take_health_snapshot()
        now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("[Nocturne] Health Snapshot"))
        self.stdout.write(_DIVIDER)

        if not services:
            self.stdout.write(self.style.WARNING("No active services found in the last hour."))
        else:
            # Fetch the freshest snapshot per service (just created by take_health_snapshot)
            for svc in sorted(services):
                snap = (
                    HealthSnapshot.objects.filter(service_name=svc)
                    .order_by("-recorded_at")
                    .first()
                )
                score = snap.health_score if snap else compute_health_score(svc)

                # Determine trend vs previous snapshot
                prev = (
                    HealthSnapshot.objects.filter(service_name=svc)
                    .order_by("-recorded_at")[1:2]
                    .first()
                )
                if prev:
                    delta = score - prev.health_score
                    if delta > 5:
                        trend = "↑ IMPROVING"
                        color = self.style.SUCCESS
                    elif delta < -5:
                        trend = "↓ DEGRADING"
                        color = self.style.ERROR
                    else:
                        trend = "→ STABLE"
                        color = self.style.WARNING
                else:
                    trend = "→ STABLE"
                    color = self.style.WARNING

                line = f"{svc:<22} {score:.0f}/100 {trend}"
                self.stdout.write(color(line))

        self.stdout.write(_DIVIDER)
        self.stdout.write(f"Snapshot saved at: {now_str}")
        self.stdout.write("")
