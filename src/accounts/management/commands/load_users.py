import csv
from django.core.management.base import BaseCommand, CommandError
from src.accounts.models import User
from src.shared.enums import UserRole

class Command(BaseCommand):
    help = "Импорт пользователей из CSV. Колонки: email,first_name,last_name,password,role(tenant|landlord)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Путь к CSV файлу")

    def handle(self, *args, **options):
        path = options["csv_path"]
        created = updated = skipped = 0

        try:
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                required = {"email", "password"}
                if not required.issubset(reader.fieldnames or []):
                    missing = required - set(reader.fieldnames or [])
                    raise CommandError(f"Отсутствуют колонки: {', '.join(missing)}")

                for row in reader:
                    email = (row.get("email") or "").strip().lower()
                    password = (row.get("password") or "").strip()
                    if not email or not password:
                        skipped += 1
                        continue

                    role = (row.get("role") or "tenant").strip().lower()
                    role = role if role in (UserRole.TENANT, UserRole.LANDLORD) else UserRole.TENANT

                    user, was_created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            "username": email,  # username технический
                            "first_name": (row.get("first_name") or "").strip(),
                            "last_name": (row.get("last_name") or "").strip(),
                            "role": role,
                        }
                    )
                    if was_created:
                        user.set_password(password)
                        user.save()
                        created += 1
                    else:
                        changed = False
                        fn = (row.get("first_name") or "").strip()
                        ln = (row.get("last_name") or "").strip()
                        if fn and user.first_name != fn:
                            user.first_name = fn; changed = True
                        if ln and user.last_name != ln:
                            user.last_name = ln; changed = True
                        if row.get("password"):
                            user.set_password(password); changed = True
                        if row.get("role") and role in (UserRole.TENANT, UserRole.LANDLORD) and user.role != role:
                            user.role = role; changed = True
                        if changed:
                            user.save(); updated += 1

        except FileNotFoundError:
            raise CommandError(f"Файл не найден: {path}")

        self.stdout.write(self.style.SUCCESS(f"Создано: {created}, Обновлено: {updated}, Пропущено: {skipped}"))
