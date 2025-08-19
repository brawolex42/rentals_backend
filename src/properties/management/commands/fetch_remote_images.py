from django.core.management.base import BaseCommand
from pathlib import Path
import re
import sys
import time
import hashlib

# используем requests для удобства
try:
    import requests
except Exception as e:
    requests = None

MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

def guess_ext(url: str, content_type: str | None) -> str:
    # 1) попробуем по URL
    m = re.search(r"\.(jpe?g|png|webp)(?:\?.*)?$", url, flags=re.IGNORECASE)
    if m:
        return "." + m.group(1).lower()
    # 2) по Content-Type
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        return MIME_TO_EXT.get(ct, ".jpg")
    return ".jpg"

def sanitize_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)

class Command(BaseCommand):
    help = "Скачивает изображения по шаблону URL или списку URL в локальную папку (по умолчанию: static/seed_images)."

    def add_arguments(self, parser):
        parser.add_argument("--url-template", type=str, default=None,
                            help="Шаблон URL, напр.: 'http://1.2.3.4/images/house_{i:03}.jpg'.")
        parser.add_argument("--start", type=int, default=1, help="Начальный i для url-template (включительно).")
        parser.add_argument("--end", type=int, default=1, help="Конечный i для url-template (включительно).")
        parser.add_argument("--urls-file", type=str, default=None, help="Путь к txt-файлу со списком URL (по одному на строку).")

        parser.add_argument("--out-dir", type=str, default="static/seed_images",
                            help="Куда сохранять (по умолчанию static/seed_images).")
        parser.add_argument("--prefix", type=str, default="remote_",
                            help="Префикс имени файлов (по умолчанию remote_).")
        parser.add_argument("--timeout", type=float, default=15.0, help="Таймаут запроса, сек (по умолчанию 15).")
        parser.add_argument("--retries", type=int, default=2, help="Повторы при неудаче (по умолчанию 2).")
        parser.add_argument("--sleep", type=float, default=0.2, help="Пауза между запросами, сек (по умолчанию 0.2).")
        parser.add_argument("--user-agent", type=str, default="Mozilla/5.0 (compatible; SeedBot/1.0)",
                            help="Заголовок User-Agent.")
        parser.add_argument("--referer", type=str, default=None, help="Заголовок Referer, если нужен.")
        parser.add_argument("--insecure", action="store_true",
                            help="Отключить проверку SSL (verify=False). Используй только при необходимости.")
        parser.add_argument("--host-header", type=str, default=None,
                            help="Принудительный Host заголовок (если сайт по IP требует Host).")

    def handle(self, *args, **opts):
        if requests is None:
            self.stderr.write(self.style.ERROR("Нужен пакет 'requests'. Установи: pip install requests"))
            return

        url_tmpl = opts.get("url_template")
        urls_file = opts.get("urls_file")
        start_i = int(opts.get("start") or 1)
        end_i = int(opts.get("end") or 1)
        out_dir = Path(opts.get("out_dir") or "static/seed_images")
        out_dir.mkdir(parents=True, exist_ok=True)

        # Собираем список URL
        urls = []
        if urls_file:
            p = Path(urls_file)
            if not p.is_file():
                self.stderr.write(self.style.ERROR(f"Файл не найден: {p}"))
                return
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                u = line.strip()
                if u and not u.startswith("#"):
                    urls.append(u)
        elif url_tmpl:
            for i in range(start_i, end_i + 1):
                try:
                    u = url_tmpl.format(i=i)
                except Exception:
                    # поддержка формата {i:03}
                    u = url_tmpl.replace("{i}", str(i))
                urls.append(u)
        else:
            self.stderr.write(self.style.ERROR("Нужно указать --url-template ИЛИ --urls-file"))
            return

        headers = {"User-Agent": opts.get("user_agent")}
        if opts.get("referer"):
            headers["Referer"] = opts["referer"]
        if opts.get("host_header"):
            headers["Host"] = opts["host_header"]

        timeout = float(opts.get("timeout") or 15.0)
        retries = int(opts.get("retries") or 2)
        sleep_s = float(opts.get("sleep") or 0.2)
        verify = not bool(opts.get("insecure"))

        saved = 0
        skipped = 0
        errors = 0

        for idx, url in enumerate(urls, start=1):
            ok = False
            last_err = None
            for attempt in range(retries + 1):
                try:
                    r = requests.get(url, headers=headers, timeout=timeout, stream=True, verify=verify)
                    if r.status_code != 200:
                        last_err = f"HTTP {r.status_code}"
                        time.sleep(sleep_s)
                        continue

                    ctype = r.headers.get("Content-Type", "")
                    if "image" not in ctype.lower():
                        last_err = f"Not an image (Content-Type: {ctype})"
                        time.sleep(sleep_s)
                        continue

                    ext = guess_ext(url, ctype)
                    # имя файла: по хэшу URL, чтобы не дублировать
                    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
                    fname = sanitize_name(f"{opts.get('prefix')}{h}{ext}")
                    fout = out_dir / fname
                    if fout.exists():
                        skipped += 1
                        ok = True
                        break

                    with open(fout, "wb") as f:
                        for chunk in r.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)

                    saved += 1
                    ok = True
                    break
                except Exception as e:
                    last_err = str(e)
                    time.sleep(sleep_s)

            if not ok:
                errors += 1
                self.stderr.write(self.style.WARNING(f"Пропущен [{idx}] {url}: {last_err}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"[{idx}] OK: {url}"))

        self.stdout.write(self.style.SUCCESS(
            f"Готово. Сохранено: {saved}, пропущено (дубликаты): {skipped}, ошибок: {errors}. "
            f"Папка: {out_dir.resolve()}"
        ))

