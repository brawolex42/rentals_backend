import polib
from pathlib import Path

base = Path(r"C:\Users\B.Nutzer\PycharmProjects\rentals_backend\locale\de\LC_MESSAGES")
po = polib.pofile(str(base / "django.po"))
po.save_as_mofile(str(base / "django.mo"))
print("OK: django.mo recompiled")
