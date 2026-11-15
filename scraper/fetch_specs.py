"""يجيب مواصفات المنتجات من صفحاتها في B.TECH و2B وكارفور وCompumarts (نون بيقفل صفحات المنتجات).

المواصفات مش بتتغير، فبنحفظها في specs.json ومنجيبهاش تاني غير بعد 60 يوم.
كل تشغيلة بتجيب عدد محدود (وقت محدود) عشان التحديث ميطوّلش.
  python scraper/fetch_specs.py          # يجيب الناقص
  python scraper/fetch_specs.py --test   # يجرب منتج من كل متجر ويطبع النتيجة
"""
import html
import json
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_prices import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "products.json"
SPECS = ROOT / "specs.json"
ORDER = ["btech", "2b", "carrefour", "compumarts"]  # الأوضح الأول
BUDGET = 9 * 60       # ثواني
MAX_ROWS = 30
SKIP = {"is online", "select from category", "ean", "barcode", "sku", "seller", "brand id", "category",
        "باركود (ean)", "is returnable", "product type", "item type"}


def clean(s):
    s = re.sub(r"<br\s*/?>", ", ", s or "")
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip(" ,")


def rows(pairs):
    out, seen = [], set()
    for k, v in pairs:
        k, v = clean(k), clean(v)
        if not k or not v or len(k) > 60 or len(v) > 300 or k.lower() in SKIP or k.lower() in seen:
            continue
        if v.lower() in ("true", "false", "n/a", "-", "none", "no data"):
            continue
        seen.add(k.lower())
        out.append([k, v])
    return out[:MAX_ROWS]


def parse_btech(h):
    m = re.search(r'specifications\\?":(\[.*?\])', h)
    if not m:
        return []
    raw = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
    try:
        items = json.loads(raw)
    except ValueError:
        return []
    return rows((i.get("key", ""), i.get("value", "")) for i in items if isinstance(i, dict))


def parse_2b(h):
    i = h.find('id="product-attribute-specs-table"')
    if i < 0:
        return []
    t = h[i:h.find("</table>", i)]
    return rows(re.findall(r'<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>', t, re.S))


def parse_carrefour(h):
    i = h.find(">Specification<")
    if i < 0:
        return []
    t = h[i:i + 60000]
    return rows(re.findall(r'font-regular w-full text-nightblack">(.*?)</div>\s*'
                           r'<div class="[^"]*font-bold w-full text-nightblack">(.*?)</div>', t, re.S))


def parse_compumarts(h):
    i = h.find('class="dark-spec-table')
    if i < 0:
        i = h.find("<table", h.find('class="product__description') if 'class="product__description' in h else 0)
    if i < 0:
        return []
    t = h[i:h.find("</table>", i)]
    return rows(re.findall(r'<tr[^>]*>\s*<t[hd][^>]*>(.*?)</t[hd]>\s*<td[^>]*>(.*?)</td>', t, re.S))


PARSERS = {"btech": parse_btech, "2b": parse_2b, "carrefour": parse_carrefour, "compumarts": parse_compumarts}


def sources(p):
    by = {o["store"]: o["url"] for o in p["offers"] if o.get("url") and o["store"] in PARSERS}
    return [(s, by[s]) for s in ORDER if s in by]


def main():
    products = json.loads(DATA.read_text(encoding="utf-8"))["products"]
    if "--test" in sys.argv:
        done = set()
        for p in products:
            for s, u in sources(p):
                if s in done:
                    continue
                done.add(s)
                try:
                    r = PARSERS[s](fetch(u))
                except Exception as e:  # noqa: BLE001
                    r = f"ERR {e}"
                print("=====", s, p["name"][:60], "\n", json.dumps(r, ensure_ascii=False)[:1500])
        return

    try:
        cache = json.loads(SPECS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    now = datetime.now(timezone.utc)
    fresh = lambda c: c and now - datetime.fromisoformat(c["t"]) < timedelta(days=60 if c.get("specs") else 7)
    todo = [p for p in products if sources(p) and not fresh(cache.get(p["id"]))]
    # المنتجات المتقارنة في متاجر أكتر الأول
    todo.sort(key=lambda p: -len({o["store"] for o in p["offers"]}))
    start, got = time.time(), 0
    for p in todo:
        if time.time() - start > BUDGET:
            break
        specs, src = [], None
        for s, u in sources(p):
            try:
                specs = PARSERS[s](fetch(u))
            except Exception as e:  # noqa: BLE001
                print(f"✗ مواصفات {p['name'][:40]} / {s}: {e}", file=sys.stderr)
            time.sleep(random.uniform(2, 4))
            if len(specs) >= 3:
                src = s
                break
        cache[p["id"]] = {"t": now.isoformat(timespec="minutes"), "source": src, "specs": specs if src else []}
        got += bool(src)
    keep = {p["id"] for p in products}
    cache = {k: v for k, v in cache.items() if k in keep}  # منتجات اتشالت
    SPECS.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    have = sum(1 for v in cache.values() if v.get("specs"))
    print(f"المواصفات: جبت {got} جديد، و{have} منتج عنده مواصفات من {len(products)}")


if __name__ == "__main__":
    main()
