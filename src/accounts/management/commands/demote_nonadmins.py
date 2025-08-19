
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Demote all non-superusers: set is_staff=False"

    def handle(self, *args, **options):
        User = get_user_model()
        qs = User.objects.filter(is_superuser=False, is_staff=True)
        n = qs.update(is_staff=False)
        self.stdout.write(f"Demoted {n} users")
