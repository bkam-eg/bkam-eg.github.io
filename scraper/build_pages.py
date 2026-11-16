"""يبني صفحة لكل منتج وصفحة لكل قسم + sitemap.xml، عشان جوجل يلاقي المنتجات.

بيشتغل بعد update_prices.py: بيقرا products.json ويكتب:
  p/<slug>.html   صفحة المنتج (أسعاره في كل المتاجر)
  c/<slug>.html   صفحة القسم (كل منتجاته بأرخص سعر)
  m/<slug>.html   «سعر <موديل> في مصر»: كل نسخ الموديل (مساحة/لون) وأرخص متجر لكل نسخة
  b/<قسم>-<ماركة>.html  «أسعار <قسم> <ماركة>» مرتبة من الأرخص
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


def product_page(p, stores, related, updated_ar, updated_iso, spec=None, family=None):
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
{f'<p class="famlink"><a href="/m/{family_slug(family[0])}.html">كل نسخ <bdi dir="ltr">{e(family_title(family[0]))}</bdi> ({family[1]}) وأسعارها ←</a></p>' if family else ''}
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


def category_page(cat, items, updated_ar, brands=()):
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
{('<p class="fams">حسب الماركة: ' + ' '.join(f'<a href="/b/{cs}-{b}.html">{e(BRAND_AR.get(b, b.capitalize()))}</a>' for b in brands) + '</p>') if brands else ''}
<ul class="clist">{''.join(lis)}</ul>
"""
    return page(title, desc, url, body, updated_ar)


# ───── صفحات «سعر <موديل> في مصر» و«أسعار <قسم> <ماركة>»: بتجمّع نسخ الموديل (مساحة/لون) في صفحة واحدة
# عشان اللي بيدوّر في جوجل على «سعر ايفون 17 برو ماكس» يلاقي كل النسخ وأرخص متجر لكل واحدة.
FAMILY_CATS = {"موبايلات", "تابلت", "ساعات ذكية", "بلايستيشن", "سماعات"}
_CUT = (r"\b(dual|single|5g|4g|lte|ram|with|smartphone|smart|mobile|international|middle|nano|esim|wifi|wi|cellular|"
        r"tablet|black|white|blue|green|silver|gold|grey|gray|titanium|pink|purple|violet|navy|olive|teal|sage|"
        r"lavender|ultramarine|mist|cosmic|midnight|starlight|deep|natural|desert|orange|red|yellow|bluetooth|"
        r"wireless|true|earbuds|headphones?|over|on|in|ear|noise|cancell?ing|anc|gps|console|edition|version|"
        r"local|official|ksa|uae|ai|smartwatch|watch(?=\s*[-,]|$))\b")
BRAND_AR = {"apple": "آبل", "samsung": "سامسونج", "xiaomi": "شاومي", "oppo": "أوبو", "realme": "ريلمي",
            "honor": "هونر", "infinix": "إنفينكس", "vivo": "فيفو", "huawei": "هواوي", "sony": "سوني", "jbl": "JBL",
            "anker": "أنكر", "lenovo": "لينوفو", "nokia": "نوكيا", "tecno": "تكنو", "motorola": "موتورولا"}
CASE = {"iphone": "iPhone", "ipad": "iPad", "airpods": "AirPods", "dualsense": "DualSense", "playstation": "PlayStation",
        "jbl": "JBL", "fe": "FE", "se": "SE", "xl": "XL", "hp": "HP", "fc": "FC", "ea": "EA"}


def brand_of(p):
    from update_prices import BRANDS  # noqa: PLC0415
    b = (p.get("brand") or "").lower()
    if b in ("", "generic"):
        w = re.findall(r"[a-z]+", p["name"].lower())
        b = next((x for x in w[:3] if x in BRANDS), "")
        if b == "redmi":
            b = "xiaomi"
    if b == "galaxy":
        b = "samsung"
    if not b and re.match(r"(?i)(iphone|ipad|airpods)", p["name"]):
        b = "apple"
    if not b and re.match(r"(?i)(galaxy)", p["name"]):
        b = "samsung"
    if not b and re.match(r"(?i)(redmi)", p["name"]):
        b = "xiaomi"
    if not b and re.match(r"(?i)(playstation|dualsense)", p["name"]):
        b = "sony"
    return b


def family_key(p):
    n = p["name"].lower().replace("+", " plus ")
    n = re.sub(r"\b(watch|buds|reno|band|note|hot|tab)(\d)", r"\1 \2", n)
    n = re.split(r"\s*[,(|–/]\s*|\s-\s", n)[0]
    n = re.split(r"\b\d+\s*(?:gb|tb|terabyte|mm|inch|\")|" + _CUT, n)[0]
    toks = [t for t in re.findall(r"[a-z0-9]+", n) if t not in ("new", "generic", "mobile")]
    b = brand_of(p)
    if toks and toks[0] == "redmi" and b == "xiaomi":
        toks = ["xiaomi"] + toks
    if b and (not toks or toks[0] != b):
        toks = [b] + toks
    if p["category"] == "ساعات ذكية" and "series" in toks and "watch" not in toks:
        toks.insert(toks.index("series"), "watch")
    if len(toks) < 2:
        return ""
    return " ".join(toks[:5])


def family_title(key):
    out = []
    for t in key.split():
        if t in CASE:
            out.append(CASE[t])
        elif re.fullmatch(r"[a-z]\d+[a-z]*", t):
            out.append(t[0].upper() + t[1:])
        else:
            out.append(t.capitalize())
    return " ".join(out)


def family_slug(key):
    return re.sub(r"[^a-z0-9]+", "-", key).strip("-")


def cheapest(p):
    av = [o for o in live(p) if avail(o)] or live(p)
    return min(av, key=lambda o: o["price"]) if av else None


def family_page(key, items, stores, updated_ar):
    title_en = family_title(key)
    url = f"{SITE}/m/{family_slug(key)}.html"
    items = sorted(items, key=lambda p: price_range(p)[0])
    best_p = items[0]
    bo = cheapest(best_p)
    store_names = {o["store"] for p in items for o in live(p)}
    rows = []
    for p in items:
        o = cheapest(p)
        n = len({x["store"] for x in live(p)})
        rows.append(f'<tr><td><a dir="auto" href="/p/{p["page"]}.html">{e(p["name"] if len(p["name"]) <= 100 else p["name"][:100].rsplit(" ", 1)[0] + "…")}</a></td>'
                    f'<td class="num">{money(o["price"])}</td><td>{e(stores.get(o["store"], {}).get("name", o["store"]))}</td>'
                    f'<td class="num">{n}</td></tr>')
    lo = price_range(best_p)[0]
    hi = max(price_range(p)[1] for p in items)
    bname = e(stores.get(bo["store"], {}).get("name", bo["store"]))
    title = f"سعر {title_en} في مصر النهارده – أرخص سعر في {len(store_names)} متاجر"
    desc = (f"أرخص سعر {title_en} في مصر النهارده {money(lo)} في {stores.get(bo['store'], {}).get('name', '')}. "
            f"قارن {len(items)} نسخة (المساحة واللون) في {len(store_names)} متاجر، والأسعار بتتحدث كل 6 ساعات.")
    cs = cat_slug(best_p["category"])
    body = f"""<nav class="crumbs"><a href="/">الرئيسية</a> › <a href="/c/{cs}.html">{e(best_p['category'])}</a> › <bdi dir="ltr">{e(title_en)}</bdi></nav>
<h1>سعر <bdi dir="ltr">{e(title_en)}</bdi> في مصر النهارده</h1>
<p class="lead">أرخص سعر دلوقتي <b>{money(lo)}</b> في <b>{bname}</b>{f"، وأغلى نسخة بـ {money(hi)}" if hi > lo else ""}.
جمعنا {len(items)} نسخة من <bdi dir="ltr">{e(title_en)}</bdi> من {len(store_names)} متاجر مصرية. اضغط على أي نسخة تشوف سعرها في كل متجر.</p>
<table class="ftable"><thead><tr><th>النسخة</th><th>أرخص سعر</th><th>المتجر</th><th>متاجر</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<section class="faq"><h2>أسئلة بتتسأل كتير</h2>
<h3>بكام <bdi dir="ltr">{e(title_en)}</bdi> في مصر النهارده؟</h3>
<p>السعر بيبدأ من {money(lo)}{f" ويوصل لـ {money(hi)} حسب المساحة واللون والمتجر" if hi > lo else ""}.</p>
<h3>فين أرخص مكان أشتري منه <bdi dir="ltr">{e(title_en)}</bdi>؟</h3>
<p>أرخص سعر دلوقتي في {bname}. الأسعار بتتغير، وإحنا بنحدّثها أوتوماتيك كل 6 ساعات.</p>
</section>
"""
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": f"سعر {title_en} في مصر",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{SITE}/p/{p['page']}.html",
                               "name": p["name"]} for i, p in enumerate(items)]}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f"بكام {title_en} في مصر النهارده؟",
         "acceptedAnswer": {"@type": "Answer", "text": f"السعر بيبدأ من {money(lo)}."}},
        {"@type": "Question", "name": f"فين أرخص مكان أشتري منه {title_en}؟",
         "acceptedAnswer": {"@type": "Answer", "text": f"أرخص سعر دلوقتي في {stores.get(bo['store'], {}).get('name', '')}."}}]}
    extra = "".join('<script type="application/ld+json">' + json.dumps(x, ensure_ascii=False).replace("</", "<\\/")
                    + "</script>\n" for x in (ld, faq))
    return page(title, desc, url, body, updated_ar, "website", (best_p.get("images") or [None])[0], extra)


def brand_page(cat, brand, items, stores, updated_ar, fams):
    bar = BRAND_AR.get(brand, brand.capitalize())
    url = f"{SITE}/b/{cat_slug(cat)}-{brand}.html"
    items = sorted(items, key=lambda p: price_range(p)[0])
    lo = price_range(items[0])[0]
    lis = "".join(f'<li><a dir="auto" href="/p/{p["page"]}.html">{e(short_name(p["name"], 110) if len(p["name"]) > 110 else p["name"])}</a>'
                  f'<span class="cp">{money(price_range(p)[0])}</span>'
                  f'<span class="cn">{e(stores.get(cheapest(p)["store"], {}).get("name", ""))}</span></li>' for p in items)
    fl = "".join(f'<a href="/m/{family_slug(k)}.html" dir="ltr">{e(family_title(k))}</a> ' for k in fams)
    title = f"أسعار {cat} {bar} في مصر النهارده – من {money(lo)}"
    desc = f"أسعار {len(items)} من {cat} {bar} في مصر، مرتبة من الأرخص، مع أرخص متجر لكل واحد. بتتحدث كل 6 ساعات."
    body = f"""<nav class="crumbs"><a href="/">الرئيسية</a> › <a href="/c/{cat_slug(cat)}.html">{e(cat)}</a> › {e(bar)}</nav>
<h1>أسعار {e(cat)} {e(bar)} في مصر</h1>
<p class="lead">{len(items)} منتج، مرتبين من الأرخص. أرخص واحد دلوقتي بـ {money(lo)}.</p>
{f'<p class="fams">الموديلات: {fl}</p>' if fl else ''}
<ul class="clist">{lis}</ul>
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

    for d in ("p", "c", "m", "b"):  # نبني من الأول عشان المنتجات اللي اتشالت صفحاتها تتشال
        shutil.rmtree(ROOT / d, ignore_errors=True)
        (ROOT / d).mkdir()

    by_cat = {}
    for p in products:
        by_cat.setdefault(p["category"], []).append(p)

    fams = {}
    for p in products:
        if p["category"] in FAMILY_CATS and (k := family_key(p)):
            fams.setdefault(k, []).append(p)
    fams = {k: v for k, v in fams.items() if len(v) >= 2}
    fam_of = {p["id"]: k for k, v in fams.items() for p in v}

    for p in products:
        same = [r for r in by_cat[p["category"]] if r is not p]
        same.sort(key=lambda r: (-len({o["store"] for o in live(r)}), abs(price_range(r)[0] - price_range(p)[0])))
        html_text = product_page(p, stores, same[:8], updated_ar, updated_iso, specs.get(p["id"]),
                                 (fam_of[p["id"]], len(fams[fam_of[p["id"]]])) if p["id"] in fam_of else None)
        (ROOT / "p" / f"{p['page']}.html").write_text(html_text, encoding="utf-8")

    for k, items in fams.items():
        (ROOT / "m" / f"{family_slug(k)}.html").write_text(family_page(k, items, stores, updated_ar), encoding="utf-8")

    brands = {}
    for p in products:
        b = brand_of(p)
        if b and b != "generic":
            brands.setdefault((p["category"], b), []).append(p)
    brands = {k: v for k, v in brands.items() if len(v) >= 3}
    for (cat, b), items in brands.items():
        fl = sorted({fam_of[p["id"]] for p in items if p["id"] in fam_of})
        (ROOT / "b" / f"{cat_slug(cat)}-{b}.html").write_text(brand_page(cat, b, items, stores, updated_ar, fl),
                                                               encoding="utf-8")
    brand_links = {}
    for (cat, b) in brands:
        brand_links.setdefault(cat, []).append(b)

    for cat, items in by_cat.items():
        (ROOT / "c" / f"{cat_slug(cat)}.html").write_text(
            category_page(cat, items, updated_ar, sorted(brand_links.get(cat, []))), encoding="utf-8")

    urls = [(f"{SITE}/", "1.0")] + [(f"{SITE}/c/{cat_slug(c)}.html", "0.8") for c in by_cat] + \
           [(f"{SITE}/m/{family_slug(k)}.html", "0.8") for k in fams] + \
           [(f"{SITE}/b/{cat_slug(c)}-{b}.html", "0.7") for c, b in brands] + \
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
    print(f"اتبنى {len(products)} صفحة منتج و{len(by_cat)} صفحة قسم و{len(fams)} صفحة موديل و{len(brands)} صفحة ماركة و sitemap فيها {len(urls)} رابط")


if __name__ == "__main__":
    main()
