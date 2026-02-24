from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.users.models import ApiKey, User


class Command(BaseCommand):
    help = "Create an API key for integration (prints the raw key once)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Existing username to attach the key to")
        parser.add_argument("--name", required=True, help="Human-friendly key name")
        parser.add_argument(
            "--scopes",
            default="templates:read,templates:write,certificates:read,certificates:write,certificates:delete,files:read",
            help="Comma-separated scopes",
        )
        parser.add_argument(
            "--expires-days",
            type=int,
            default=0,
            help="Optional expiry in N days (0 = never)",
        )

    def handle(self, *args, **options):
        username: str = options["username"]
        name: str = options["name"]
        scopes_raw: str = options["scopes"]
        expires_days: int = options["expires_days"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User not found: {username}") from exc

        scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
        if not scopes:
            raise CommandError("At least one scope is required.")

        expires_at = None
        if expires_days and expires_days > 0:
            expires_at = timezone.now() + timezone.timedelta(days=expires_days)

        _api_key, raw_key = ApiKey.create_with_raw_key(
            name=name,
            user=user,
            scopes=scopes,
            expires_at=expires_at,
        )

        self.stdout.write(self.style.SUCCESS("API key created."))
        self.stdout.write("\nIMPORTANT: Save this key now. It will not be shown again.\n")
        self.stdout.write(raw_key)
