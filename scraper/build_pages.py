"""يبني صفحة لكل منتج وصفحة لكل قسم + sitemap.xml، عشان جوجل يلاقي المنتجات.

بيشتغل بعد update_prices.py: بيقرا products.json ويكتب:
  p/<slug>.html   صفحة المنتج (أسعاره في كل المتاجر)
  c/<slug>.html   صفحة القسم (كل منتجاته بأرخص سعر)
  sitemap.xml, robots.txt
وبيضيف لكل منتج في products.json حقل "page" عشان الصفحة الرئيسية تربط بيه.
"""
import hashlib
import os
import subprocess
import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
# رابط الموقع من اسم الريبو (<اسم>.github.io)، عشان لو اسم الحساب اتغير الروابط تتظبط لوحدها
_repo = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1]
if not _repo:
    try:
        _repo = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True,
                               cwd=Path(__file__).resolve().parent).stdout.strip().rstrip("/").split("/")[-1]
    except OSError:
        _repo = ""
    _repo = _repo.removesuffix(".git")
SITE = "https://" + (_repo if _repo.endswith(".github.io") else "bkam.github.io")
DATA = ROOT / "products.json"
SPECS = ROOT / "specs.json"  # من fetch_specs.py

# أسماء أقسام إنجليزي للرابط (الرابط العربي بيبقى طويل ومش مقروء لما يتنسخ)
CAT_SLUG = {"موبايلات": "mobiles", "تابلت": "tablets", "لابتوب": "laptops", "تلفزيونات": "tvs",
            "شاشات كمبيوتر": "monitors", "كمبيوتر": "computer", "بلايستيشن": "playstation", "سماعات": "headphones",
            "ساعات ذكية": "smart-watches", "إكسسوارات موبايل": "mobile-accessories",
            "أجهزة منزلية": "home-appliances", "أجهزة مطبخ": "kitchen-appliances"}

AR_DIGITS = str.maketrans("0123456789,", "٠١٢٣٤٥٦٧٨٩٬")
e = lambda s: html.escape(str(s), quote=True)


def money(n):
    return f"{int(n):,}".translate(AR_DIGITS) + " ج.م"


def short_name(name, limit=70):
    """اسم المنتج من غير التفاصيل الزيادة (لعنوان الصفحة)."""
    n = re.split(r"\s[-–|]\s|,|\(|\sWith\s", name, maxsplit=1)[0].strip()
    if len(n) < 12:
        n = name
    return (n[:limit].rsplit(" ", 1)[0] + "…") if len(n) > limit else n


def slugify(p):
    words = re.findall(r"[a-z0-9]+", f"{p.get('brand', '')} {p['name']}".lower())
    seen, out = set(), []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)
    base = "-".join(out[:9]) or "product"
    return f"{base}-{hashlib.md5(p['id'].encode()).hexdigest()[:6]}"


def cat_slug(c):
    return CAT_SLUG.get(c) or "cat-" + hashlib.md5(c.encode()).hexdigest()[:6]


def live(p):
    return [o for o in p["offers"] if o.get("price", 0) > 0]


def avail(o):
    return o.get("price", 0) > 0 and o.get("in_stock") is not False


def price_range(p):
    v = [o["price"] for o in live(p) if avail(o)] or [o["price"] for o in live(p)]
    return (min(v), max(v)) if v else (0, 0)


HEAD = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
{og_image}<meta property="og:locale" content="ar_EG">
<meta property="og:site_name" content="بكام؟">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Readex+Pro:wght@500;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600&display=swap">
<link rel="stylesheet" href="/page.css">
<script>try{{if(JSON.parse(localStorage.getItem("skam")||"{{}}").owner)document.documentElement.classList.add("owner")}}catch(e){{}}</script>
{extra}</head>
<body>
<header class="top"><div class="wrap"><a class="logo" href="/"><span>بكام</span>؟</a>
<a class="back" href="/">كل المنتجات ←</a></div></header>
<main class="wrap">
"""

FOOT = """</main>
<footer class="wrap">آخر تحديث للأسعار: {updated} · الأسعار بتتحدث أوتوماتيك كل 6 ساعات، وممكن تتغير في المتجر.
الموقع ممكن ياخد عمولة من بعض المتاجر من غير ما السعر يزيد عليك.</footer>
</body>
</html>
"""


def page(title, desc, url, body, updated, og_type="website", image=None, extra=""):
    og_image = f'<meta property="og:image" content="{e(image)}">\n' if image else ""
    return (HEAD.format(title=e(title), desc=e(desc), url=e(url), og_type=og_type, og_image=og_image, extra=extra)
            + body + FOOT.format(updated=e(updated)))


def offer_url(p, o, stores):
    if o.get("url"):
        return o["url"]  # الرابط زي ما هو (روابط كارفور فيها offer= ولازم تفضل)
    s = stores.get(o["store"], {})
    return (s.get("search") or "https://www.google.com/search?q=") + re.sub(r"\s+", "+", p.get("search") or p["name"])


def specs_html(spec, stores):
    if not spec or not spec.get("specs"):
        return ""
    rows = "".join(f'<tr><th dir="auto">{e(k)}</th><td dir="auto">{e(v)}</td></tr>' for k, v in spec["specs"])
    src = stores.get(spec.get("source"), {}).get("name", spec.get("source") or "")
    return (f'<section class="specs"><h2>المواصفات</h2><table>{rows}</table>'
            f'<p class="hint">المواصفات منقولة من صفحة المنتج في {e(src)}، واتأكد منها في المتجر قبل الشراء.</p></section>')


# ---------- الاسم بالعربي (الناس بتدوّر "سعر ايفون 17 برو ماكس") ----------
AR_PHRASES = [("air conditioner", "تكييف"), ("air fryer", "قلاية هوائية"), ("washing machine", "غسالة"),
              ("power bank", "باور بانك"), ("smart tv", "شاشة سمارت"), ("smart watch", "ساعة ذكية"),
              ("smart band", "سمارت باند"), ("macbook air", "ماك بوك اير"), ("macbook pro", "ماك بوك برو"),
              ("playstation 5", "بلايستيشن 5"), ("coffee machine", "ماكينة قهوة"), ("galaxy tab", "جالاكسي تاب"),
              ("galaxy buds", "جالاكسي بادز"), ("galaxy watch", "جالاكسي ووتش"), ("apple watch", "ابل ووتش"),
              ("hair dryer", "سشوار"), ("front load", "تحميل امامي"), ("top load", "تحميل علوي"),
              ("split air conditioner", "تكييف سبليت"), ("wall charger", "شاحن حيطة")]
AR_WORDS = {
    "apple": "ابل", "iphone": "ايفون", "ipad": "ايباد", "macbook": "ماك بوك", "airpods": "ايربودز",
    "samsung": "سامسونج", "galaxy": "جالاكسي", "xiaomi": "شاومي", "redmi": "ريدمي", "poco": "بوكو",
    "note": "نوت", "oppo": "اوبو", "reno": "رينو", "realme": "ريلمي", "honor": "هونر", "infinix": "انفينكس",
    "hot": "هوت", "vivo": "فيفو", "huawei": "هواوي", "pro": "برو", "max": "ماكس", "plus": "بلس", "ultra": "الترا",
    "mini": "ميني", "air": "اير", "lite": "لايت", "slim": "سليم", "sony": "سوني", "playstation": "بلايستيشن",
    "ps5": "بلايستيشن 5", "dualsense": "دوال سينس", "controller": "دراع", "portal": "بورتال", "jbl": "جي بي ال",
    "anker": "انكر", "charger": "شاحن", "logitech": "لوجيتك", "mouse": "ماوس", "lenovo": "لينوفو",
    "ideapad": "ايديا باد", "victus": "فيكتوس", "asus": "اسوس", "tuf": "تاف", "dell": "ديل", "hp": "اتش بي", "lg": "ال جي",
    "tcl": "تي سي ال", "tv": "شاشة", "laptop": "لابتوب", "monitor": "شاشة كمبيوتر", "tablet": "تابلت",
    "tab": "تاب", "pad": "باد", "buds": "بادز", "earbuds": "سماعة", "headphones": "سماعة", "headset": "سماعة",
    "refrigerator": "ثلاجة", "fridge": "ثلاجة", "sharp": "شارب", "carrier": "كاريير", "fresh": "فريش",
    "philips": "فيليبس", "tefal": "تيفال", "fryer": "قلاية", "blender": "خلاط", "nespresso": "نسبريسو",
    "band": "باند", "watch": "ساعة", "gaming": "جيمنج", "tune": "تيون", "series": "سيريس", "oled": "OLED",
    "toshiba": "توشيبا", "split": "سبليت", "inverter": "انفرتر", "odyssey": "اوديسي", "baseus": "باسيوس",
    "espresso": "اسبريسو", "huawei": "هواوي", "cooling": "تبريد", "heating": "تسخين", "wireless": "لاسلكي",
    "conditioner": "تكييف", "smartphone": "موبايل", "phone": "موبايل", "unionaire": "يونيون اير", "hisense": "هايسنس", "fc": "FC"}
AR_UNITS = {"gb": "جيجا", "tb": "تيرا", "inch": "بوصة", "hp": "حصان", "kg": "كيلو", "l": "لتر", "mah": "مللي امبير"}


def arabic_name(p, sname):
    """اسم المنتج بالعربي من الكلمات المعروفة؛ لو مفيش ولا كلمة معروفة نرجّع فاضي."""
    t = " " + sname.lower().replace("-", " ").replace("‑", " ") + " "
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(gb|tb|inch|hp|kg|mah|l)\b", lambda m: f" {m.group(1)}§{m.group(2)} ", t)
    t = re.sub(r'(\d+(?:\.\d+)?)\s*(?:"|”|-?inch(?:es)?)', lambda m: f" {m.group(1)}§inch ", t)
    # Reno16 = Reno 16 ، Watch8 = Watch 8
    t = re.sub(r"\b([a-z]{3,})(\d+[a-z]?)\b", lambda m: f"{m.group(1)} {m.group(2)}" if m.group(1) in AR_WORDS else m.group(0), t)
    t = re.sub(r"\b(\d+)(?:st|nd|rd|th)\s*gen(?:eration)?\b", r" _الجيل_\1 ", t)
    for en, ar in sorted(AR_PHRASES, key=lambda x: -len(x[0])):
        t = t.replace(f" {en} ", f" _{ar.replace(' ', '_')} ")
    out, known, after_code = [], 0, False
    for w in re.findall(r"[^\s,()/|+]+", t):
        if "§" in w:
            n, u = w.split("§")
            out.append(f"{n} {AR_UNITS[u]}")
        elif "_" in w:
            out.append(w.replace("_", " ").strip()); known += 1
        elif w in AR_WORDS:
            out.append(AR_WORDS[w]); known += 1
        elif re.fullmatch(r"[a-z]?\d+[a-z]{0,3}", w):  # أرقام وموديلات قصيرة زي 17 و A56
            if not after_code:
                out.append(w.upper())
        elif re.fullmatch(r"[a-z]+", w):
            continue  # كلمة إنجليزي مش معروفة (Optimax, Essential…): نسيبها، الاسم الإنجليزي جنبها
        else:
            after_code = True  # كود موديل طويل (38QHCT12DN-708): مش محتاجينه ولا الرقم اللي بعده
            continue
        if len(out) >= 7:
            break
    while out and out[-1] == "اير":  # "Air" لوحدها في الآخر (من غير Conditioner) ملهاش معنى
        out.pop()
    brand = (p.get("brand") or "").lower()
    if out and brand in AR_WORDS and AR_WORDS[brand] not in out[0] and known < 2:
        out.insert(0, AR_WORDS[brand]); known += 1
    return " ".join(out) if known >= 1 and len(out) >= 2 else ""


def product_page(p, stores, related, updated_ar, updated_iso, spec=None):
    name = p["name"]
    sname = short_name(name)
    lo, hi = price_range(p)
    offers = sorted(live(p), key=lambda o: (not avail(o), o["price"]))
    store_names = [stores.get(o["store"], {}).get("name", o["store"]) for o in offers]
    url = f"{SITE}/p/{p['page']}.html"
    multi = len({o["store"] for o in offers}) > 1
    ar = arabic_name(p, sname)
    title = (f"سعر {ar} في مصر | {sname}" if ar else f"سعر {sname} في مصر") + \
        (f" – قارن {len(set(store_names))} متاجر" if multi else "")
    desc = (f"سعر {ar or sname}{f' ({sname})' if ar else ''} في مصر النهارده يبدأ من {money(lo)}"
            + (f" وبيوصل لـ {money(hi)}" if hi > lo else "")
            + f". قارن الأسعار في {' و'.join(dict.fromkeys(store_names))} واشتري من الأرخص.")
    img = next(iter(p.get("images") or []), None)

    rows = []
    for o in offers:
        s = stores.get(o["store"], {"name": o["store"]})
        best = avail(o) and o["price"] == lo
        pills = ('<span class="pill best">الأرخص</span>' if best else "") + \
                ('<span class="pill out">غير متوفر</span>' if not avail(o) else "") + \
                ('<span class="pill old">آخر سعر معروف</span>' if o.get("stale") else "")
        was = f'<s>{money(o["old_price"])}</s>' if (o.get("old_price") or 0) > o["price"] else ""
        rows.append(f'<li class="offer{" best" if best else ""}{" off" if not avail(o) else ""}">'
                    f'<span class="store">{e(s["name"])}{pills}</span>'
                    f'<span class="price">{was}{money(o["price"])}</span>'
                    f'<a class="buy" href="{e(offer_url(p, o, stores))}" target="_blank" rel="noopener sponsored">اشتري من {e(s["name"])}</a></li>')

    save = f'<p class="save">توفّر لحد {money(hi - lo)} لو اشتريت من الأرخص</p>' if hi > lo else ""
    imgs = "".join(f'<img src="{e(u)}" alt="{e(sname)}" loading="lazy" referrerpolicy="no-referrer" '
                   f'onerror="this.remove()">' for u in (p.get("images") or [])[:1])
    rel = "".join(f'<li><a dir="auto" href="/p/{r["page"]}.html">{e(short_name(r["name"], 60))}</a>'
                  f'<span>{money(price_range(r)[0])}</span></li>' for r in related)
    cs = cat_slug(p["category"])
    body = f"""<nav class="crumbs"><a href="/">الرئيسية</a> › <a href="/c/{cs}.html">{e(p['category'])}</a></nav>
<article class="product">
<div class="pimg">{imgs}</div>
<div class="pinfo">
{f'<h1>سعر {e(ar)}</h1><p class="en" dir="ltr">{e(name)}</p>' if ar else f'<h1>سعر <bdi dir="ltr">{e(name)}</bdi></h1>'}
<p class="range">{"من " + money(lo) + " لـ " + money(hi) if hi > lo else money(lo)}</p>
{save}
<ul class="offers">{''.join(rows)}</ul>
<p class="hint">الأسعار مرتبة من الأرخص. اتأكد من السعر واللون والمساحة في صفحة المتجر قبل ما تشتري.</p>
</div>
</article>
{specs_html(spec, stores)}
{f'<section class="related"><h2>منتجات تانية في {e(p["category"])}</h2><ul>{rel}</ul></section>' if rel else ''}
"""
    ld = {"@context": "https://schema.org", "@type": "Product", "name": name, "category": p["category"],
          "offers": {"@type": "AggregateOffer", "priceCurrency": "EGP", "lowPrice": lo, "highPrice": hi,
                     "offerCount": len(offers)}}
    if img:
        ld["image"] = img
    if p.get("brand") and p["brand"] != "Generic":
        ld["brand"] = {"@type": "Brand", "name": p["brand"]}
    extra = ('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
             + "</script>\n")
    return page(title, desc, url, body, updated_ar, "product", img, extra)


def category_page(cat, items, updated_ar):
    cs = cat_slug(cat)
    url = f"{SITE}/c/{cs}.html"
    items = sorted(items, key=lambda p: (-len({o["store"] for o in live(p)}), price_range(p)[0]))
    lis = []
    for p in items:
        lo, hi = price_range(p)
        n = len({o["store"] for o in live(p)})
        lis.append(f'<li><a dir="auto" href="/p/{p["page"]}.html">{e(short_name(p["name"], 80))}</a>'
                   f'<span class="cp">{money(lo)}</span>'
                   f'<span class="cn">{"في " + str(n) + " متاجر" if n > 1 else "متجر واحد"}</span></li>')
    title = f"أسعار {cat} في مصر – قارن بين المتاجر"
    desc = f"قارن أسعار {len(items)} منتج في قسم {cat} في نون وأمازون وB.TECH و2B وكارفور، واعرف فين الأرخص."
    body = f"""<nav class="crumbs"><a href="/">الرئيسية</a> › {e(cat)}</nav>
<h1>أسعار {e(cat)} في مصر</h1>
<p class="lead">{len(items)} منتج، مرتبين بالأكتر مقارنة. اضغط على أي منتج تشوف سعره في كل متجر.</p>
<ul class="clist">{''.join(lis)}</ul>
"""
    return page(title, desc, url, body, updated_ar)


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    try:
        specs = json.loads(SPECS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        specs = {}
    products = data["products"]
    stores = data["stores"]
    updated_iso = data.get("updated") or datetime.utcnow().isoformat(timespec="minutes")
    try:
        dt = datetime.fromisoformat(updated_iso).astimezone(ZoneInfo("Africa/Cairo"))
        updated_ar = dt.strftime("%Y-%m-%d %H:%M") + " بتوقيت القاهرة"
    except ValueError:
        updated_ar = updated_iso
    day = updated_iso[:10]

    products = [p for p in products if live(p)]
    used = set()
    for p in products:
        s = slugify(p)
        while s in used:
            s += "x"
        used.add(s)
        p["page"] = s

    for d in ("p", "c"):  # نبني من الأول عشان المنتجات اللي اتشالت صفحاتها تتشال
        shutil.rmtree(ROOT / d, ignore_errors=True)
        (ROOT / d).mkdir()

    by_cat = {}
    for p in products:
        by_cat.setdefault(p["category"], []).append(p)

    for p in products:
        same = [r for r in by_cat[p["category"]] if r is not p]
        same.sort(key=lambda r: (-len({o["store"] for o in live(r)}), abs(price_range(r)[0] - price_range(p)[0])))
        html_text = product_page(p, stores, same[:8], updated_ar, updated_iso, specs.get(p["id"]))
        (ROOT / "p" / f"{p['page']}.html").write_text(html_text, encoding="utf-8")

    for cat, items in by_cat.items():
        (ROOT / "c" / f"{cat_slug(cat)}.html").write_text(category_page(cat, items, updated_ar), encoding="utf-8")

    urls = [(f"{SITE}/", "1.0")] + [(f"{SITE}/c/{cat_slug(c)}.html", "0.8") for c in by_cat] + \
           [(f"{SITE}/p/{p['page']}.html", "0.6") for p in products]
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{day}</lastmod><priority>{pr}</priority></url>\n" for u, pr in urls)
        + "</urlset>\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")

    # الصفحة الرئيسية بتربط كل منتج بصفحته وكل قسم بصفحته
    slugs = {p["id"]: p["page"] for p in products}
    for p in data["products"]:
        if p["id"] in slugs:
            p["page"] = slugs[p["id"]]
    data["category_pages"] = {c: cat_slug(c) for c in by_cat}
    # روابط الأقسام في الصفحة الرئيسية كـ HTML عادي (جوجل بيقراها من غير JavaScript)
    idx = ROOT / "index.html"
    links = "أسعار: " + " ".join(f'<a href="c/{cat_slug(c)}.html">{e(c)}</a>' for c in by_cat)
    idx.write_text(re.sub(r"<!--CATS-->.*?<!--/CATS-->", lambda m: f"<!--CATS-->{links}<!--/CATS-->",
                          idx.read_text(encoding="utf-8"), flags=re.S), encoding="utf-8")
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"اتبنى {len(products)} صفحة منتج و{len(by_cat)} صفحة قسم و sitemap فيها {len(urls)} رابط")


if __name__ == "__main__":
    main()
