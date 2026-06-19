from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a user with 'nocturne.view_nocturne' permission."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="nocturne_viewer",
            help="Username for the viewer account (default: nocturne_viewer)",
        )
        parser.add_argument(
            "--password",
            default="nocturne123",
            help="Password for the viewer account (default: nocturne123)",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        username = options["username"]
        password = options["password"]
        User     = get_user_model()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"is_active": True, "is_staff": False, "is_superuser": False},
        )
        user.set_password(password)
        user.save()

        try:
            perm = Permission.objects.get(
                codename="view_nocturne",
                content_type__app_label="nocturne",
            )
        except Permission.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                "Permission 'nocturne.view_nocturne' not found. "
                "Run 'python manage.py migrate' first."
            ))
            return

        user.user_permissions.add(perm)

        action   = "Created" if created else "Updated"
        login_url = getattr(settings, "NOCTURNE", {}).get("LOGIN_URL", "/admin/login/")

        self.stdout.write(self.style.SUCCESS(f"[Nocturne] {action} user: {username}"))
        self.stdout.write(f"[Nocturne] Password: {password}")
        self.stdout.write(f"[Nocturne] Permission assigned: nocturne.view_nocturne")
        self.stdout.write(f"[Nocturne] Login at: {login_url}")
