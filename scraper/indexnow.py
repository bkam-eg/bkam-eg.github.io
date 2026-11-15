"""يبلّغ Bing وYandex (عن طريق IndexNow) بالصفحات اللي اتغيرت في آخر تحديث.

  python scraper/indexnow.py --staged --list > changed.txt   (قبل الـ commit: الصفحات اللي اتغيرت فعلاً)
  python scraper/indexnow.py $(cat changed.txt)             (بعد النشر: يبلّغ عنها)
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pages import SITE  # noqa: E402

KEY = "ef227cde17e4b1574b7d277774dea619"  # نفس اسم الملف ef227cde17e4b1574b7d277774dea619.txt في جذر الموقع


def really_changed(f):
    """الصفحة اتغير فيها حاجة غير سطر "آخر تحديث"؟ (من git diff --cached)"""
    d = subprocess.run(["git", "diff", "--cached", "-U0", "--", f], capture_output=True, text=True).stdout
    lines = [l for l in d.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    return any("آخر تحديث" not in l for l in lines) if d else False


def main():
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--staged" in sys.argv:  # الملفات الجاهزة للـ commit، من غير اللي اتغير فيها التاريخ بس
        names = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True).stdout.split()
        files = [f for f in names if really_changed(f) or subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{f}"], capture_output=True).returncode]
    if "--all" in sys.argv:  # كل الصفحات (أول مرة)
        files = ["index.html"] + [str(f) for d in ("c", "p") for f in sorted(Path(d).glob("*.html"))]
    if "--list" in sys.argv:  # بس اطبع الملفات (قبل الـ commit)، والتبليغ بعد ما الموقع يتنشر
        print("\n".join(files))
        return
    urls = []
    for f in files:
        if f.startswith(("p/", "c/")) and f.endswith(".html") and Path(f).exists():
            urls.append(f"{SITE}/{f}")
        elif f == "index.html":
            urls.append(f"{SITE}/")
    if not urls:
        print("IndexNow: مفيش صفحات اتغيرت")
        return
    body = json.dumps({"host": SITE.split("//")[1], "key": KEY, "keyLocation": f"{SITE}/{KEY}.txt",
                       "urlList": urls[:10000]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: بلّغت عن {len(urls)} صفحة (HTTP {r.status})")
    except Exception as e:  # noqa: BLE001  (مش مشكلة لو فشل، جوجل وBing بيقروا الـ sitemap برضه)
        print(f"IndexNow: فشل ({e})")


if __name__ == "__main__":
    main()
