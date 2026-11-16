"""يدوّر على منتجاتنا في متاجر مالهاش بحث ينفع، عن طريق خريطة الموقع (sitemap).

كل متجر بينشر ملف فيه لينكات كل منتجاته (عشان محركات البحث). بنحمّله، ولكل منتج عندنا
بندوّر على اسمه في اللينكات دي محلياً، ونفتح بس الصفحات الشبهه ونقرا منها الاسم والسعر
(البيانات المنظمة schema.org اللي في الصفحة). لو نفس المنتج، بنحفظ اللينك في links.json،
وتحديث الأسعار بيفتح اللينكات المحفوظة كل مرة ويحدّث سعرها.

  python scraper/discover.py          # يدوّر على المنتجات اللي لسه متدوّرش عليها
  python scraper/discover.py --test   # يجرب كام منتج ويطبع النتيجة من غير ما يحفظ
"""
import gzip
import html
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
from urllib.robotparser import RobotFileParser

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_prices as up  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "links.json"
BUDGET = int(os.environ.get("DISCOVER_BUDGET", 40 * 60))  # ثواني
RETRY_DAYS = 7      # منتج ملقيناهوش في متجر؟ نجرب تاني بعد أسبوع
MAX_PAGES = 3       # أقصى عدد صفحات نفتحها لكل منتج في كل متجر

# المتاجر: خريطة الموقع + شكل لينك المنتج
SITEMAP_STORES = {
    "vodafone": {"name": "فودافون", "maps": ["https://eshop.vodafone.com.eg/sitemap-en.xml"],
                 "product": r"/en/prod/"},
    "raya": {"name": "راية شوب", "maps": ["https://www.rayashop.com/en-sitemap.xml"],
             "product": r"rayashop\.com/en/[a-z0-9-]*\d[a-z0-9-]*$"},
    "raneen": {"name": "رنين", "maps": ["https://www.raneen.com/sitemap/sitemap_en.xml"],
               "product": r"raneen\.com/en/[^/]+\.html$|raneen\.com/en/[a-z0-9-]*\d[a-z0-9-]*$"},
    "zs": {"name": "زهران ستور", "maps": ["https://zs-eg.com/sitemap_index.xml"],
           "product": r"/en/product/[a-z0-9-]*\d[a-z0-9-]*/?$", "submap": r"product-sitemap"},
    "elghazawy": {"name": "الغزاوي", "maps": ["https://elghazawy.com/sitemap.xml"],
                  "product": r"/en/product/\d+/"},
    "kimo": {"name": "كيمو ستور", "maps": ["https://kimostore.net/sitemap.xml"],
             "product": r"kimostore\.net/products/", "submap": r"sitemap_products"},
    "alfrensia": {"name": "الفرنسية", "maps": ["https://alfrensia.com/sitemap_index.xml"],
                  "product": r"/en/product/", "submap": r"product-sitemap"},
    "mobilemasr": {"name": "موبايل مصر", "maps": ["https://mobilemasr.com/__sitemap__/en-US.xml"],
                   "product": r"/en/products/show/.*-new-"},
    "halan": {"name": "حالا", "maps": ["https://shop.halan.com/sitemap/active_products"],
              "product": r"shop\.halan\.com/ar/", "rewrite": ("/ar/", "/en/")},
    # متاجر عندنا بحثها، بس البحث ساعات مبيلاقيش المنتج: نكمّل من خريطة الموقع
    "btech": {"name": "B.TECH", "maps": ["https://btech.com/sitemap.xml"],
              "product": r"btech\.com/ar/p/", "rewrite": ("/ar/", "/en/")},
    "2b": {"name": "2B", "maps": ["https://2b.com.eg/en_sitemap.xml"],
           "product": r"2b\.com\.eg/en/[a-z0-9-]*\d[a-z0-9-]*\.html$"},
    "xprs": {"name": "XPRS", "maps": ["https://myxprs.com/sitemap.xml"],
             "product": r"myxprs\.com/products/", "submap": r"sitemap_products"},
}

_robots = {}


def allowed(url):
    base = re.match(r"https?://[^/]+", url).group(0)
    if base not in _robots:
        rp = RobotFileParser()
        try:
            rp.parse(up.fetch(base + "/robots.txt").splitlines())
        except Exception:  # noqa: BLE001
            rp = None
        _robots[base] = rp
    rp = _robots[base]
    return rp is None or rp.can_fetch("*", url)


def get_xml(url):
    r = up.http.get(url, impersonate="chrome", timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    b = r.content
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    return b.decode("utf-8", "ignore")


def product_urls(store):
    cfg = SITEMAP_STORES[store]
    todo, urls, seen = list(cfg["maps"]), [], set()
    while todo and len(seen) < 40:
        m = todo.pop(0)
        if m in seen:
            continue
        seen.add(m)
        try:
            xml = get_xml(m)
        except Exception as e:  # noqa: BLE001
            print(f"✗ {store}: sitemap {m}: {e}", file=sys.stderr)
            continue
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
            loc = html.unescape(loc)
            if re.search(r"\.xml(\.gz)?(\?|$)", loc):
                if not cfg.get("submap") or re.search(cfg["submap"], loc):
                    todo.append(loc)
            elif re.search(cfg["product"], loc):
                if cfg.get("rewrite"):
                    loc = loc.replace(*cfg["rewrite"], 1)
                urls.append(loc)
        time.sleep(1)
    return list(dict.fromkeys(urls))


def slug_text(url):
    path = unquote(url.split("?")[0].rstrip("/").rsplit("/", 1)[-1].replace("+", " "))
    path = re.sub(r"\.html$", "", path)
    return re.sub(r"[-_]+", " ", path)


def tokens(text):
    return {w for w in up.keywords(text) if w not in up.STOP and len(w) > 1}


class Index:
    """فهرس كلمات للينكات المتجر، عشان نلاقي المرشحين بسرعة من غير ما نقارن بكل اللينكات."""

    def __init__(self, urls):
        self.urls = urls
        self.toks = [tokens(slug_text(u)) for u in urls]
        self.inv = defaultdict(list)
        for i, ts in enumerate(self.toks):
            for t in ts:
                self.inv[t].append(i)

    def candidates(self, name, n=MAX_PAGES):
        want = tokens(name)
        score = defaultdict(float)
        for t in want:
            hits = self.inv.get(t, [])
            if not hits or len(hits) > 3000:
                continue
            w = 1 / (1 + len(hits)) ** 0.5  # الكلمة النادرة (كود موديل) أهم من الكلمة المنتشرة
            if any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
                w *= 3
            for i in hits:
                score[i] += w
        best = sorted(score, key=lambda i: -score[i])[:n * 4]
        # نتأكد بقواعد المطابقة بتاعتنا على الاسم اللي في اللينك (لو اللينك فيه اسم)
        out = []
        for i in best:
            s = slug_text(self.urls[i])
            if len(tokens(s)) >= 3 and up.similar(name, s) < 0.3:
                continue
            out.append(self.urls[i])
            if len(out) >= n:
                break
        return out


def _price(v):
    try:
        return round(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def read_page(url):
    """يقرا الاسم والسعر من البيانات المنظمة (schema.org Product) في صفحة المنتج."""
    page = up.fetch(url)
    for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for it in items:
            if not isinstance(it, dict):
                continue
            t = it.get("@type")
            if t != "Product" and not (isinstance(t, list) and "Product" in t):
                continue
            offers = it.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = _price(offers.get("price") or offers.get("lowPrice"))
            if not price:
                continue
            img = it.get("image")
            if isinstance(img, list):
                img = img[0] if img else ""
            if isinstance(img, dict):
                img = img.get("url", "")
            avail = str(offers.get("availability", ""))
            return {"name": html.unescape(str(it.get("name", ""))).strip(), "price": price,
                    "image": img or "", "in_stock": "OutOfStock" not in avail and "SoldOut" not in avail}
    return None


UNITS = ("gb", "tb", "mm", "l", "kg", "hp", "inch", "w", "mah", "hz")


def units(text):
    """القيم بوحداتها: {"gb": {"256gb","12gb"}, "inch": {"55inch"}, ...}"""
    out = defaultdict(set)
    for w in up.keywords(text):
        m = re.fullmatch(r"\d+(" + "|".join(UNITS) + ")", w)
        if m:
            out[m.group(1)].add(w)
    return out


def first_word(text):
    m = re.match(r"\W*([a-z0-9+\-]+)", text.lower())
    return m.group(1) if m else ""


def check(p, info):
    """نفس المنتج؟ نفس قواعد المطابقة بين المتاجر + الماركة + الأرقام بوحداتها + السعر قريب."""
    if not info or not info["name"]:
        return 0
    ref = p.get("brand", "") + " " + p["name"]
    name, low = info["name"], info["name"].lower()
    # الماركة: ماركة منتجنا لازم تكون في اسم المنتج التاني، وأول كلمة فيه لو ماركة لازم تكون عندنا
    brand = (p.get("brand") or "").strip().lower() or first_word(p["name"])
    if brand in up.BRANDS and brand != "generic" and brand not in low:
        return 0
    fw = first_word(name)
    if fw in up.BRANDS and fw != "generic" and fw not in ref.lower():
        return 0
    # نفس الوحدة بأرقام مختلفة = منتج تاني (12GB غير 8GB رام، 40mm غير 44mm، 7L غير 4L)
    ua, ub = units(ref), units(name)
    for u in UNITS:
        if ua[u] and ub[u] and ua[u] != ub[u] and not (u in ("gb", "w") and (ua[u] < ub[u] or ub[u] < ua[u])):
            return 0
    sim = up.similar(ref, info["name"])
    live = [o["price"] for o in p["offers"] if not o.get("stale")] or [o["price"] for o in p["offers"]]
    if sim >= 0.5 and up.close_price(live, info["price"]):
        return sim
    return 0


def main(test=False):
    data = json.loads(up.OUTPUT.read_text(encoding="utf-8"))
    products = data["products"]
    try:
        links = json.loads(LINKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        links = {}
    now = datetime.now(timezone.utc)
    deadline = time.time() + BUDGET

    def work(store):
        found = tried = 0
        try:
            urls = product_urls(store)
        except Exception as e:  # noqa: BLE001
            print(f"✗ {store}: {e}", file=sys.stderr)
            return store, 0, 0
        print(f"• {store}: {len(urls)} لينك منتج في خريطة الموقع")
        if not urls:
            return store, 0, 0
        idx = Index(urls)
        todo = []
        for p in products:
            if any(o["store"] == store for o in p["offers"]):
                continue
            rec = links.get(p["id"], {}).get(store)
            if rec and (rec.get("url") or (now - datetime.fromisoformat(rec["t"])).days < RETRY_DAYS):
                continue
            todo.append(p)
        # المنتجات اللي في متجر واحد بس الأول
        todo.sort(key=lambda p: len({o["store"] for o in p["offers"]}))
        if test:
            todo = todo[:6]
        for p in todo:
            if time.time() > deadline:
                break
            ref = p.get("brand", "") + " " + p["name"]
            best = None
            for url in idx.candidates(ref):
                if not allowed(url):
                    continue
                try:
                    info = read_page(url)
                except Exception as e:  # noqa: BLE001
                    print(f"  ✗ {store}: {url[:80]}: {e}", file=sys.stderr)
                    info = None
                time.sleep(random.uniform(1.5, 3))
                sim = check(p, info)
                if test:
                    print(f"    {store} «{p['name'][:40]}» ← «{(info or {}).get('name', '—')[:50]}» "
                          f"{(info or {}).get('price')} تشابه {sim:.2f}")
                if sim and (not best or sim > best[0]):
                    best = (sim, url, info)
                    if sim >= 0.9:
                        break
            tried += 1
            rec = {"t": now.isoformat(timespec="minutes")}
            if best:
                found += 1
                rec["url"] = best[1]
                print(f"  ↳ {store}: «{p['name'][:45]}» = «{best[2]['name'][:45]}» بـ {best[2]['price']:,}")
            links.setdefault(p["id"], {})[store] = rec
        return store, found, tried

    with ThreadPoolExecutor(len(SITEMAP_STORES)) as pool:
        results = list(pool.map(work, SITEMAP_STORES))
    for store, found, tried in results:
        print(f"{store}: لقيت {found} من {tried} منتج")
    if not test:
        ids = {p["id"] for p in products}
        links = {k: v for k, v in links.items() if k in ids}  # نشيل المنتجات اللي اتشالت من الموقع
        LINKS.write_text(json.dumps(links, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        total = sum(1 for v in links.values() for r in v.values() if r.get("url"))
        print(f"links.json: {total} لينك محفوظ")


if __name__ == "__main__":
    main(test="--test" in sys.argv)
