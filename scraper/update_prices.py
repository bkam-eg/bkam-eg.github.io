"""
بيحدّث products.json لوحده.

لكل كلمة بحث في searches.csv:
  1. يبحث في نون وأمازون مصر ويجيب أول نتايج (الاسم، السعر، الصورة، التوفر، اللينك).
  2. يطابق المنتج الواحد بين المتجرين بالاسم.
  3. يكتب النتيجة في products.json اللي الموقع بيقرا منه.

لو متجر فشل، بيحتفظ بآخر أسعار معروفة ليه ويعلّم عليها "قديم".
"""
import csv
import html as htmllib
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from curl_cffi import requests as http

ROOT = Path(__file__).resolve().parent.parent
SEARCHES = ROOT / "searches.csv"
BROWSE = ROOT / "browse.csv"  # أقسام بناخدها من نون كاملة وندوّر على كل منتج فيها في الباقي
OUTPUT = ROOT / "products.json"
PER_STORE = 8  # كام نتيجة من كل متجر لكل كلمة

STORES = {
    "noon":   {"name": "نون",        "affiliate": False, "search": "https://www.noon.com/egypt-en/search/?q="},
    "amazon": {"name": "أمازون مصر", "affiliate": False, "search": "https://www.amazon.eg/s?k="},
    "btech":  {"name": "B.TECH",     "affiliate": False, "search": "https://btech.com/en/s?q="},
    "2b":     {"name": "2B",         "affiliate": False, "search": "https://2b.com.eg/en/catalogsearch/result/?q="},
    "carrefour": {"name": "كارفور",  "affiliate": False, "search": "https://www.carrefouregypt.com/mafegy/en/search?keyword="},
    "compumarts": {"name": "Compumarts", "affiliate": False, "search": "https://www.compumarts.com/search?q="},
    "xprs": {"name": "XPRS", "affiliate": False, "search": "https://myxprs.com/search?type=product&q="},
    "tradeline": {"name": "تريدلاين", "affiliate": False, "search": "https://tradelinestores.com/search?type=product&q="},
    "dream2000": {"name": "دريم 2000", "affiliate": False, "search": "https://dream2000.com/en/search?type=product&q="},
    "alsheikh": {"name": "الشيخ", "affiliate": False, "search": "https://alsheikhstores.com/en/search?type=product&q="},
    "miami":  {"name": "ميامي سنتر", "affiliate": False, "search": "https://miamicenters.com/?post_type=product&s="},
    # متاجر بنلاقي منتجاتها من خريطة الموقع (discover.py) مش من البحث
    "vodafone": {"name": "فودافون", "affiliate": False, "search": "https://eshop.vodafone.com.eg/en/"},
    "raya":   {"name": "راية شوب", "affiliate": False, "search": "https://www.rayashop.com/en/"},
    "raneen": {"name": "رنين", "affiliate": False, "search": "https://www.raneen.com/en/"},
    "zs":     {"name": "زهران ستور", "affiliate": False, "search": "https://zs-eg.com/en/"},
    "elghazawy": {"name": "الغزاوي", "affiliate": False, "search": "https://elghazawy.com/en/"},
    "kimo":   {"name": "كيمو ستور", "affiliate": False, "search": "https://kimostore.net/search?q="},
    "alfrensia": {"name": "الفرنسية", "affiliate": False, "search": "https://alfrensia.com/en/?s="},
    "mobilemasr": {"name": "موبايل مصر", "affiliate": False, "search": "https://mobilemasr.com/en/"},
    "halan":  {"name": "حالا", "affiliate": False, "search": "https://shop.halan.com/en/"},
    "jumia":  {"name": "جوميا",      "affiliate": False, "search": "https://www.jumia.com.eg/catalog/?q="},
}


def fetch(url, tries=3):
    for attempt in range(tries):
        try:
            r = http.get(url, impersonate="chrome" if attempt == 0 else "safari17_0", timeout=40,
                         headers={"Accept-Language": "en-US,en;q=0.9,ar;q=0.8"})
        except Exception as e:  # الاتصال اتقطع
            if attempt == tries - 1:
                raise RuntimeError(f"الاتصال اتقطع: {str(e)[:60]}")
            time.sleep(10 + random.uniform(0, 5))
            continue
        if r.status_code == 200:
            return r.text
        if r.status_code in (429, 503) and attempt < tries - 1:
            wait = 20 * (attempt + 1) + random.uniform(0, 10)
            print(f"  … HTTP {r.status_code}، هستنى {wait:.0f} ثانية وأجرب تاني")
            time.sleep(wait)
            continue
        raise RuntimeError(f"HTTP {r.status_code}")


def money(s):
    if s is None:
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(s))
    if not m:
        return None
    n = float(m.group(0).replace(",", ""))
    return round(n) if n > 0 else None


# ---------- نون ----------

def search_noon(q, limit=PER_STORE, page_no=1):
    page = fetch(STORES["noon"]["search"] + quote_plus(q) + (f"&page={page_no}" if page_no > 1 else ""))
    start = page.find("hits:")
    if start < 0:
        raise RuntimeError("شكل صفحة نون اتغير (ملقتش النتايج)")
    chunks = page[start:].split('{offer_code:"')[1:]
    out = []
    for c in chunks:
        c = c[:4000]
        code = c.split('"', 1)[0]
        def field(name, pat=r'"((?:[^"\\]|\\.)*)"'):
            m = re.search(r'[{,]' + name + r':' + pat, "," + c)
            return m.group(1) if m else None
        name = field("name")
        sku = field("sku")
        slug = field("url")
        price = money(field("sale_price", r"([\d.]+)")) or money(field("price", r"([\d.]+)"))
        if not (name and sku and slug and price):
            continue
        buy = field("is_buyable", r"(!0|!1|true|false)")
        brand = field("brand")
        out.append({
            "store": "noon",
            "brand": json.loads(f'"{brand}"') if brand else "Generic",
            "name": json.loads(f'"{name}"'),
            "price": price,
            "old_price": money(field("price", r"([\d.]+)")),
            "image": json.loads(f'"{field("image_url") or ""}"'),
            "url": f"https://www.noon.com/egypt-en/{slug}/{sku}/p/?o={code}",
            "in_stock": buy not in ("!1", "false"),
            "key": "noon:" + sku,
        })
        if len(out) >= limit:
            break
    return out


# ---------- أمازون ----------

def search_amazon(q):
    page = fetch(STORES["amazon"]["search"] + quote_plus(q) + "&language=en_AE")
    if "triggerInterstitialChallenge" in page or re.search(r"captcha", page[:5000], re.I):
        raise RuntimeError("أمازون طلب تحقق (اتقفل)")
    blocks = re.split(r'(?=<div[^>]*data-component-type="s-search-result")', page)[1:]
    out = []
    for b in blocks:
        b = b[:30000]
        asin = re.search(r'data-asin="([A-Z0-9]{10})"', b)
        if not asin or "AdHolder" in b[:600] or ">Sponsored<" in b:
            continue
        title = re.search(r'<h2[^>]*aria-label="([^"]+)"', b) or \
            re.search(r'<h2[^>]*>.*?<span[^>]*>([^<]+)</span>', b, re.S)
        price = re.search(r'<span class="a-price"[^>]*>\s*<span class="a-offscreen">([^<]+)<', b)
        old = re.search(r'<span class="a-price a-text-price"[^>]*>\s*<span class="a-offscreen">([^<]+)<', b)
        img = re.search(r'<img[^>]+class="s-image"[^>]+src="([^"]+)"', b)
        if not (title and price):
            continue
        name = htmllib.unescape(title.group(1)).strip()
        name = re.sub(r"^Sponsored Ad - ", "", name)
        out.append({
            "store": "amazon",
            "name": name,
            "price": money(price.group(1)),
            "old_price": money(old.group(1)) if old else None,
            "image": img.group(1) if img else "",
            "url": f"https://www.amazon.eg/dp/{asin.group(1)}",
            "in_stock": True,  # أمازون مش بيعرض سعر لغير المتوفر
            "key": "amazon:" + asin.group(1),
        })
        if len(out) >= PER_STORE:
            break
    return out


# ---------- B.TECH ----------

def search_btech(q):
    page = fetch("https://btech.com/en/s?q=" + quote_plus(q))
    data = page.replace('\\"', '"')
    out, seen = [], set()
    for m in re.finditer(r'\{"variant_id":"[^"]+","product_id":"[^"]+"', data):
        c = data[m.start():m.start() + 3000]
        name = re.search(r'"name":"((?:[^"\\]|\\.)*)"', c)
        brand = re.search(r'"brand":"((?:[^"\\]|\\.)*)"', c)
        price = re.search(r'"final_price":([\d.]+)', c)
        base = re.search(r'"base_price":([\d.]+)', c)
        stock = re.search(r'"is_in_stock":(true|false)', c)
        thumb = re.search(r'"thumbnail_url":"([^"]+)"', c)
        vid = re.search(r'"variant_id":"([^"]+)"', c).group(1)
        # رابط المنتج: أول "slug" قبل "categories" (اللي بعدها slugs الأقسام)، ومعاه رقم العرض
        head = c[:c.find('"categories"')] if '"categories"' in c else c[:1500]
        slug = re.search(r'"slug":"([^"]+)"', head)
        offer = re.search(r'"offer_id":"([^"]+)"', head)
        sku = re.search(r'"sku":"([^"]+)"', c)
        if not (name and price and sku) or sku.group(1) in seen:
            continue
        seen.add(sku.group(1))
        out.append({
            "store": "btech",
            "brand": brand.group(1) if brand else "",
            "name": name.group(1),
            "price": money(price.group(1)),
            "old_price": money(base.group(1)) if base else None,
            "image": "https://media.btech.com/catalogs/" + thumb.group(1) if thumb else "",
            "url": (f"https://btech.com/en/p/{slug.group(1)}" + (f"?offering_id={offer.group(1)}" if offer else ""))
                   if slug else "https://btech.com/en/s?q=" + quote_plus(q),
            "in_stock": not stock or stock.group(1) == "true",
            "key": "btech:" + sku.group(1),
        })
        if len(out) >= PER_STORE:
            break
    if not out and re.search(r"captcha|Just a moment", page[:5000], re.I):
        raise RuntimeError("B.TECH طلب تحقق (اتقفل)")
    return out  # لو مفيش نتايج، ده معناه إن المنتج مش عندهم


# ---------- 2B ----------

def search_2b(q):
    page = fetch("https://2b.com.eg/en/catalogsearch/result/?q=" + quote_plus(q))
    out = []
    parts = page.split('class="product-item-link"')
    for i, c in enumerate(parts[1:], 1):
        c = c[:6000]
        img = re.findall(r'class="product-image-photo[^"]*"\s+src="([^"]+)"', parts[i - 1][-4000:])
        link = re.search(r'href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>', c)
        price = re.search(r'data-price-amount="([\d.]+)"[^>]*data-price-type="finalPrice"', c) or \
            re.search(r'data-price-type="finalPrice"[^>]*data-price-amount="([\d.]+)"', c)
        old = re.search(r'data-price-amount="([\d.]+)"[^>]*data-price-type="oldPrice"', c)
        if not (link and price):
            continue
        out.append({
            "store": "2b",
            "name": htmllib.unescape(link.group(2)),
            "price": money(price.group(1)),
            "old_price": money(old.group(1)) if old else None,
            "image": img[-1] if img else "",
            "url": link.group(1),
            "in_stock": "out-of-stock" not in c[:3000] and "unavailable" not in c[:3000],
            "key": "2b:" + link.group(1).rstrip("/").rsplit("/", 1)[-1][:80],
        })
        if len(out) >= PER_STORE:
            break
    return out


# ---------- Compumarts (Shopify) ----------

def search_compumarts(q):
    data = json.loads(fetch("https://www.compumarts.com/search/suggest.json?resources[type]=product"
                            f"&resources[limit]={min(PER_STORE, 10)}&q=" + quote_plus(q)))
    out = []
    for p in data["resources"]["results"]["products"]:
        price = money(p.get("price"))
        if not price:
            continue
        old = money(p.get("compare_at_price_max"))
        out.append({
            "store": "compumarts",
            "brand": p.get("vendor") or "",
            "name": htmllib.unescape(p["title"]),
            "price": price,
            "old_price": old if old and old > price else None,
            "image": p.get("image") or "",
            "url": "https://www.compumarts.com/products/" + p["handle"],
            "in_stock": bool(p.get("available")),
            "key": "compumarts:" + p["handle"][:80],
        })
    return out[:PER_STORE]


# ---------- كارفور ----------

def search_carrefour(q):
    page = fetch("https://www.carrefouregypt.com/mafegy/en/search?keyword=" + quote_plus(q))
    data = page.replace('\\"', '"')
    # الصور وحالة المخزون موجودين في بيانات مخفية جوه الصفحة، مش في الـ HTML
    images = {pid: url for pid, url in re.findall(
        r'"productCompositeId":"(\d+)\|[^"]*","imageUrl":"(https://[^"]+)"', data)}
    stock = {pid: st for st, pid in re.findall(
        r'"stockLevelStatus":"(\w+)"\},"productCompositeId":"(\d+)\|', data)}
    out = []
    for m in re.finditer(r'<a[^>]+href="(/mafegy/en/[^"]+/p/(\d+)[^"]*)"[^>]*><span[^>]*>([^<]+)</span></a>'
                         r'<div[^>]*>(.{0,600}?)</div>', page):
        prices = re.findall(r'>([\d,]+(?:\.\d+)?)</span>', m.group(4))
        if not prices:
            continue
        vals = [money(p) for p in prices if money(p)]
        out.append({
            "store": "carrefour",
            "name": htmllib.unescape(m.group(3)),
            "price": min(vals),
            "old_price": max(vals) if len(vals) > 1 else None,
            "image": images.get(m.group(2), ""),
            "url": "https://www.carrefouregypt.com" + htmllib.unescape(m.group(1)),
            "in_stock": stock.get(m.group(2), "inStock").lower() != "outofstock",
            "key": "carrefour:" + m.group(2),
        })
        if len(out) >= PER_STORE:
            break
    return out


# ---------- متاجر Shopify (دريم 2000، الشيخ) ----------
# صفحة البحث فيها كل المنتجات كـ JSON (ShopifyAnalytics meta): الاسم، الماركة، وكل variant بسعره

def search_shopify(store, base, q, limit=60, lang="/en"):
    page = fetch(f"{base}{lang}/search?type=product&q=" + quote_plus(q))
    m = re.search(r"var meta = (\{.*?\});\s*\n", page) or re.search(r"var meta = (\{.*?\});", page)
    if not m:
        return []
    try:
        meta = json.loads(m.group(1))
    except ValueError:
        return []
    out = []
    for prod in meta.get("products") or []:
        handle = prod.get("handle")
        if not handle:
            continue
        img = re.search(r'href="' + lang + '/products/' + re.escape(handle) + r'[^"]*".{0,4000}?<img[^>]+src="(//[^"]+)"', page, re.S)
        for v in prod.get("variants") or []:
            name = v.get("name") or ""
            if not name or not v.get("price") or re.search(r"\bunpaid tax|customs fees", name, re.I):
                continue  # "UnPaid Taxes" نسخة مستوردة من غير ضريبة، مش نفس المنتج الرسمي
            out.append({
                "store": store, "brand": prod.get("vendor") or "", "name": name.replace(" / ", " , "),
                "price": round(v["price"] / 100), "old_price": None,
                "image": ("https:" + img.group(1).split("&amp;")[0]) if img else "",
                "url": f"{base}{lang}/products/{handle}?variant={v['id']}",
                "in_stock": True, "key": f"{store}:{v['id']}",
            })
            if len(out) >= limit:
                return out
    return out


def search_dream2000(q):
    return search_shopify("dream2000", "https://dream2000.com", q)


def search_alsheikh(q):
    return search_shopify("alsheikh", "https://alsheikhstores.com", q)


def search_xprs(q):
    return search_shopify("xprs", "https://myxprs.com", q, lang="")


def search_tradeline(q):
    return search_shopify("tradeline", "https://tradelinestores.com", q, lang="")


# ---------- ميامي سنتر (WooCommerce Store API: JSON رسمي ومفتوح) ----------

def search_miami(q):
    data = json.loads(fetch("https://miamicenters.com/wp-json/wc/store/v1/products?per_page="
                            f"{min(PER_STORE, 20)}&search=" + quote_plus(q)))
    out = []
    for it in data:
        pr = it.get("prices") or {}
        unit = 10 ** int(pr.get("currency_minor_unit") or 0)
        price = int(pr.get("price") or 0) / unit
        if not price:
            continue
        reg = int(pr.get("regular_price") or 0) / unit
        brands = it.get("brands") or []
        out.append({
            "store": "miami", "brand": brands[0].get("name", "") if brands and isinstance(brands[0], dict) else "",
            "name": htmllib.unescape(it.get("name") or ""), "price": round(price),
            "old_price": round(reg) if reg > price else None,
            "image": (it.get("images") or [{}])[0].get("src", ""),
            "url": it.get("permalink") or "", "in_stock": it.get("is_in_stock", True) is not False,
            "key": f"miami:{it.get('id')}",
        })
    return out


SEARCHERS = {"noon": search_noon, "amazon": search_amazon, "btech": search_btech,
             "2b": search_2b, "carrefour": search_carrefour, "compumarts": search_compumarts,
             "dream2000": search_dream2000, "alsheikh": search_alsheikh, "miami": search_miami,
             "xprs": search_xprs, "tradeline": search_tradeline}


# ---------- المطابقة بين المتاجر ----------

STOP = set("for with the and of to in by new original official version edition wireless "
           "gaming console controller ps5 ps playstation 5 pack bundle egypt uae ksa "
           "warranty international black white sony apple samsung xiaomi anker jbl logitech "
           "lenovo hp dell huawei oppo realme honor infinix tecno nokia electronic arts ea sports".split())
COLORS = set("black white red blue green grey gray silver gold pink purple yellow orange "
             "camouflage camo midnight cosmic starlight volcanic chroma sterling indigo teal".split())


PANELS = set("oled qled rgb nanocell neo".split())
VARIANTS = set("pro max plus ultra mini edge lite fe slim digital disc air se neo prime classic".split())


BRANDS = set("sony apple samsung xiaomi redmi anker jbl logitech lenovo hp dell huawei oppo realme "
             "honor infinix tecno nokia havit baseus ugreen oraimo joyroom lg razer hyperx redragon "
             "corsair steelseries soundcore beats bose marshall amazfit garmin generic "
             # أجهزة منزلية وتلفزيونات وشاشات
             "fresh zanussi toshiba sharp midea carrier haier tcl hisense ata jac tornado kenwood moulinex tefal "
             "philips braun bosch beko unionaire whirlpool ariston electrolux kiriazi universal hoover black+decker "
             "arzum nespresso delonghi gree white-point whitepoint daewoo panasonic viewsonic msi asus acer aoc benq "
             "ravpower vivo motorola nothing google oneplus".split())
# إكسسوار (جراب، اسكرينة، ستاند...) عمره ما يتدمج مع الجهاز نفسه
ACCESSORY = set("case cases cover covers protector tempered glass skin skins sticker sleeve pouch holder "
                "mount stand bumper film jacket backcover strap straps dock grip grips decal".split())
GENERIC_NUM = {"ps5", "ps4", "5g", "4g", "usb", "3a", "2", "1"}


def keywords(name):
    """الكلمات المهمة بالترتيب (أول الاسم هو اللي فيه الموديل عادةً)."""
    n = name.lower()
    n = re.sub(r"(?<=\b[a-z])-(?=[a-z]{3,})", "", n)  # E-train = Etrain
    n = re.sub(r"play\s*station\s*5|\bps\s*5\b", " ps5 ", n)
    n = re.sub(r"\bdisk\b", "disc", n)
    # "256/8" أو "256/8GB" = مساحة 256GB ورام 8GB ، و"256G" = 256GB (مش 5G الشبكة)
    n = re.sub(r"\b(16|32|64|128|256|512)\s*/\s*(\d{1,2})\s*(?:gb)?\b", r"\1gb \2gb", n)
    n = re.sub(r"\b(\d{1,2})\s*/\s*(64|128|256|512)\s*(?:gb)?\b", r"\2gb \1gb", n)
    n = re.sub(r"\b(16|32|64|128|256|512)\s?g\b", r"\1gb", n)
    n = re.sub(r"\b1\s?t\b", "1tb", n)
    # وحدات بأشكال مختلفة = نفس الوحدة (100 Hertz = 100Hz، 27" = 27 inch، 5 Millisecond = 5ms)
    for pat, unit in ((r"hertz", "hz"), (r"milli\s*seconds?|msec", "ms"), (r"inches|inch|in\b(?!\s*(?:black|white|\d))|\"|”|″|''", "inch"),
                      (r"litres?|liters?|ltr", "l"), (r"watts?", "w"), (r"kilograms?|kgs?", "kg"),
                      (r"terabytes?", "tb"), (r"gigabytes?", "gb"), (r"horse\s*power", "hp")):
        n = re.sub(r"(?<![a-z\d.])(\d+(?:\.\d+)?)\s*-?\s*(?:" + pat + r")", r"\1" + unit, n)
    n = re.sub(r"(\d+)\s+(gb|tb|mah|w|mm|inch|hz|k|ms|l|kg|hp)\b", r"\1\2", n)
    n = re.sub(r"(\d+)\.(\d+)(inch|l|hp|kg)", r"\1\2\3", n)  # 23.8inch = 238inch (كلمة واحدة)
    n = re.sub(r"\bdual\s+sense\b", "dualsense", n)
    n = re.sub(r"\blight\s+sync\b", "lightsync", n)
    return re.findall(r"[a-z0-9]+", n)


def is_accessory(name):
    return bool(set(keywords(name)) & ACCESSORY)


def close_price(prices, price):
    """السعر قريب من أسعار المنتج التانية؟ (جراب بـ 599 مش هو موبايل بـ 65 ألف)"""
    prices = sorted(x for x in prices if x and x > 0)
    if not prices or not price:
        return True
    mid = prices[len(prices) // 2]
    return 0.6 <= price / mid <= 1.6  # نفس المنتج نادراً ما سعره يفرق أكتر من كده بين متجرين


UNIT = re.compile(r"\d+(gb|tb|mah|hz|w|mm|cm|inch|ms|kg|l|mp|rpm|bar|liter|litre|hp)$")


def model_codes(words):
    """أكواد الموديل الطويلة: حروف وأرقام مع بعض، 6 حروف أو أكتر، ومش وحدة قياس."""
    return {w for w in words if len(w) >= 6 and sum(c.isdigit() for c in w) >= 2
            and sum(c.isalpha() for c in w) >= 2 and not UNIT.fullmatch(w) and not re.fullmatch(r"\d+x\d+", w)}


def similar(a, b):
    wa, wb = keywords(a), keywords(b)
    ta, tb = set(wa), set(wb)
    if bool(ta & ACCESSORY) != bool(tb & ACCESSORY):
        return 0
    if ta & VARIANTS != tb & VARIANTS:  # iPhone 16 غير iPhone 16 Pro
        return 0
    ka = [w for w in wa if w not in STOP][:8]
    kb = [w for w in wb if w not in STOP][:8]
    if not ka or not kb:
        return 0
    sa, sb = set(ka), set(kb)
    # أول لون مذكور هو لون المنتج نفسه (اللي بعده غالبًا لون الحزام أو العلبة)
    ca = next((w for w in wa if w in COLORS), None)
    cb = next((w for w in wb if w in COLORS), None)
    if ca and cb and ca != cb and {ca, cb} != {"grey", "gray"}:
        return 0
    if ("wired" in ta) != ("wired" in tb) and ("wireless" in ta or "wireless" in tb):
        return 0
    # ماركات مختلفة = منتجات مختلفة
    head = lambda w: set(w[:next((i for i, x in enumerate(w) if x in ("for", "compatible", "with")), len(w))])
    ba, bb = head(wa) & BRANDS, head(wb) & BRANDS
    if ba and bb and not (ba & bb):
        return 0
    # نفس كود الموديل الكامل (زي LS27D302GAUXEN أو SE2225HM) = نفس المنتج،
    # حتى لو كل متجر كاتب المواصفات بطريقته (100Hz و 100 Hertz)
    ma, mb = model_codes(wa), model_codes(wb)
    if ma and mb:
        if any(x in y or y in x for x in ma for y in mb):
            return 0.95  # نفس الموديل (أو نفس الكود ومعاه لاحقة المنطقة زي AUXEG)
        return 0  # كل واحد ليه كود موديل مختلف = منتجين مختلفين (MRA55R85 غير 55S85HA)
    # شاشات: OLED غير QLED غير Micro RGB
    if ({"tv", "monitor"} & ta) and ({"tv", "monitor"} & tb) and (ta & PANELS) != (tb & PANELS):
        return 0
    # أرقام مختلفة (مقاس، مساحة، سنة الموديل) = منتجات مختلفة
    na = {w for w in sa if any(c.isdigit() for c in w)} - GENERIC_NUM
    nb = {w for w in sb if any(c.isdigit() for c in w)} - GENERIC_NUM
    if na and nb and not (na <= nb or nb <= na):
        return 0
    score = len(sa & sb) / len(sa | sb)
    if na & nb and any(c.isalpha() for w in na & nb for c in w):
        score += 0.3  # كود موديل مشترك زي G102 أو A56
    return score


def merge(results, category, query):
    """يحوّل نتايج المتاجر لمنتجات، وكل منتج فيه عروض من أكتر من متجر."""
    products = []
    for r in sorted(results, key=lambda x: x["store"] != "noon"):
        best, score = None, 0
        for p in products:
            if any(o["store"] == r["store"] for o in p["offers"]):
                continue
            s = similar(p.get("brand", "") + " " + p["name"], r.get("brand", "") + " " + r["name"])
            if s > score and close_price([o["price"] for o in p["offers"]], r["price"]):
                best, score = p, s
        offer = {k: r[k] for k in ("store", "price", "old_price", "url", "in_stock")}
        if best and score >= 0.5:
            best["offers"].append(offer)
            if r["image"] and r["image"] not in best["images"]:
                best["images"].append(r["image"])
        else:
            products.append({
                "brand": r.get("brand", ""),
                "id": r["key"].replace(":", "-"),
                "name": r["name"],
                "category": category,
                "search": query,
                "images": [r["image"]] if r["image"] else [],
                "offers": [offer],
            })
    return products


# ---------- التشغيل ----------

ANCHORS = 6          # كام منتج من كل كلمة ندوّر عليه بالاسم في باقي المتاجر
SECOND_REF = 3       # كام منتج من B.TECH نضيفه للمرجع في كل قسم (موجود في محلات كتير، فبيتقارن أكتر من منتجات نون)
MAX_FAILS = 4        # متجر فشل كذا مرة ورا بعض؟ نوقفه لحد التشغيل الجاي


def squash(text):
    return re.sub(r"[^a-z0-9]", "", text.lower().replace("playstation 5", "ps5"))


def relevant(query, name):
    """النتيجة لازم يكون فيها أغلب كلمات البحث (المتاجر ساعات بترجع حاجات ملهاش علاقة)."""
    need = [w for w in re.findall(r"[a-z0-9]+", query.lower().replace("playstation 5", "ps5"))
            if len(w) >= 3 or any(c.isdigit() for c in w)]
    if is_accessory(name) and not is_accessory(query):
        return False  # بندوّر على الجهاز، مش على جرابه
    if {"watch", "smartwatch"} & set(keywords(name)) and "watch" not in query.lower():
        return False  # ساعة "Health Monitoring" مش شاشة كمبيوتر
    if not need:
        return True
    have = squash(name)
    hits = sum(1 for w in need if w in have)
    return hits >= max(1, -(-len(need) * 6 // 10))  # 60% على الأقل


def global_merge(products):
    """يدمج نفس المنتج لو اتجاب من متاجر مختلفة أو تحت كلمات بحث مختلفة.
    لو نفس المتجر عنده المنتج أكتر من مرة (بايعين مختلفين)، بنسيب الأرخص."""
    products.sort(key=lambda p: -len(p["offers"]))
    kept = []
    for p in products:
        stores = {o["store"] for o in p["offers"]}
        target = None
        for k in kept:
            score = similar(k.get("brand", "") + " " + k["name"], p.get("brand", "") + " " + p["name"])
            overlap = stores & {o["store"] for o in k["offers"]}
            if not close_price([o["price"] for o in k["offers"]],
                               sorted(o["price"] for o in p["offers"])[len(p["offers"]) // 2]):
                continue
            if score >= 0.85 or (score >= 0.5 and not overlap):
                target = k
                break
        if not target:
            kept.append(p)
            continue
        for o in p["offers"]:
            same = next((x for x in target["offers"] if x["store"] == o["store"]), None)
            if not same:
                target["offers"].append(o)
            elif (o.get("in_stock") is not False, -o["price"]) > (same.get("in_stock") is not False, -same["price"]):
                target["offers"][target["offers"].index(same)] = o
        for img in p.get("images", []):
            if img not in target.setdefault("images", []):
                target["images"].append(img)
    return kept


def short_query(p):
    """نسخة أقصر: الماركة + الموديل (أول 4 كلمات + رقم الموديل لو موجود)، من غير مساحة ولون."""
    words = [w for w in targeted_query(p).split() if not re.fullmatch(r"\d+(gb|tb|mah|w)", w, re.I)]
    short = words[:4]
    code = next((w for w in words[4:] if re.search(r"\d{4,}", w)), None)
    return " ".join(short + ([code] if code else []))


def targeted_query(p):
    """اسم قصير ودقيق للبحث بيه في متجر تاني: الماركة + أول كلمات الاسم."""
    name = re.sub(r"\(.*?\)|\[.*?\]|\|.*$", " ", p["name"])
    name = re.split(r"\s[-–,]\s|,", name)[0] if len(name) > 60 else name
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+.]*", name)[:7]
    brand = (p.get("brand") or "").strip()
    if brand and brand.lower() != "generic" and brand.lower() not in [w.lower() for w in words]:
        words.insert(0, brand)
    return " ".join(words)


LINKS = ROOT / "links.json"


def refresh_links(products):
    """اللينكات اللي discover.py لقاها من خريطة موقع المتاجر: نفتحها ونحدّث سعرها."""
    try:
        links = json.loads(LINKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    from discover import read_page, check  # noqa: PLC0415
    jobs = {}
    used = {o["url"].split("?")[0] for p in products for o in p["offers"]}
    for p in products:
        have = {o["store"] for o in p["offers"]}
        for store, rec in links.get(p["id"], {}).items():
            if rec.get("url") and store not in have and rec["url"].split("?")[0] not in used:
                jobs.setdefault(store, []).append((p, rec["url"]))

    added = {}  # لينك واحد ممكن يتربط بمنتجين قريبين (Shatoura/Duetto): نسيبه للأقرب بس

    def work(store):
        got = 0
        for p, url in jobs[store]:
            if time.time() > DEADLINE + 10 * 60:
                break
            try:
                info = read_page(url)
            except Exception as e:  # noqa: BLE001
                print(f"✗ {store}: {url[:70]}: {e}", file=sys.stderr)
                info = None
            time.sleep(random.uniform(1.5, 3))
            if info and check(p, info):
                added.setdefault(url, []).append((similar(p.get("brand", "") + " " + p["name"], info["name"]), p, info))
                got += 1
        return store, got, len(jobs[store])

    with ThreadPoolExecutor(max(1, len(jobs))) as pool:
        for store, got, n in pool.map(work, jobs):
            print(f"لينكات {store}: اتحدّث {got} من {n}")
    store_of = {url: s for s, js in jobs.items() for _, url in js}
    for url, cands in added.items():
        _, p, info = max(cands, key=lambda c: c[0])
        p["offers"].append({"store": store_of[url], "price": info["price"], "old_price": None,
                            "url": url, "in_stock": info["in_stock"]})
        if info["image"] and info["image"] not in p.get("images", []):
            p.setdefault("images", []).append(info["image"])


KEEP_DAYS = 14  # منتج اختفى من النتايج؟ صفحته تفضل بآخر سعر أسبوعين بدل ما تبقى 404 في جوجل


def keep_missing(products, old, now):
    """المنتجات اللي كانت موجودة واختفت المرة دي (نون رجع/وقف، المتجر غيّر الترتيب…)."""
    ids = {p["id"] for p in products}
    urls = {o["url"].split("?")[0] for p in products for o in p["offers"]}
    out = []
    for p in old:
        if p["id"] in ids or any(o["url"].split("?")[0] in urls for o in p.get("offers", [])):
            continue
        name = p.get("brand", "") + " " + p["name"]
        if any(q.get("category") == p.get("category") and similar(name, q.get("brand", "") + " " + q["name"]) >= 0.9
               for q in products + out):
            continue  # نفس المنتج موجود بنسخة جديدة
        try:
            seen = datetime.fromisoformat(p.get("seen") or "")
        except ValueError:
            seen = now  # منتج قديم من قبل الحقل ده: نبدأ نعدّ من دلوقتي
        if (now - seen).days >= KEEP_DAYS:
            continue
        out.append({**p, "seen": seen.isoformat(timespec="minutes"),
                    "offers": [{**o, "stale": True} for o in p["offers"]]})
        ids.add(p["id"])
        urls.update(o["url"].split("?")[0] for o in p["offers"])
    return out


DEADLINE = time.time() + 95 * 60  # الشغلانة ليها ساعتين؛ نسيب وقت للحفظ


def main():
    global PER_STORE
    try:
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
        old = [] if old.get("demo") else old.get("products", [])
    except (OSError, ValueError):
        old = []

    rows = [r for r in csv.DictReader(SEARCHES.open(encoding="utf-8-sig")) if (r.get("search") or "").strip()] \
        if SEARCHES.exists() else []
    products, seen, ok, failed = [], set(), 0, []
    fails = {s: 0 for s in SEARCHERS}

    cache = {}

    def run(store, query):
        nonlocal ok
        if fails[store] >= MAX_FAILS or time.time() > DEADLINE:
            return None  # بعد الوقت المسموح بنكمّل بالقديم بدل ما الشغلانة كلها تتلغي
        if (store, query) in cache:  # نفس البحث اتعمل قبل كده
            return list(cache[(store, query)])
        try:
            found = SEARCHERS[store](query)
            cache[(store, query)] = list(found)
            ok += 1
            fails[store] = 0  # بنعدّ الفشل المتتالي بس
            return found
        except Exception as e:  # noqa: BLE001
            fails[store] += 1
            failed.append(f"{query} / {store}: {e}")
            print(f"✗ {query} / {store}: {e}", file=sys.stderr)
            return None
        finally:
            time.sleep(random.uniform(1.5, 3))

    def fill(refs, live):
        """البحث الموجّه: كل منتج مرجعي ندوّر عليه بالاسم في المتاجر اللي ملقيناهوش فيها."""
        jobs = {}  # لكل متجر: المنتجات اللي ناقصاه
        for p in refs:
            for store in live:
                if not any(o["store"] == store for o in p["offers"]):
                    jobs.setdefault(store, []).append(p)

        def targeted(store):
            out = []
            for p in jobs[store]:
                found = run(store, targeted_query(p))
                if found == []:  # مفيش ولا نتيجة: متاجر زي 2B محتاجة اسم أقصر
                    short = short_query(p)  # متاجر زي 2B مبترجعش حاجة لو الاسم طويل
                    if short and short != targeted_query(p):
                        found = run(store, short)
                out.append((p, found or []))
            return out

        with ThreadPoolExecutor(max(1, len(jobs))) as pool:
            hits = list(pool.map(targeted, jobs))
        for store, pairs in zip(jobs, hits):
            # كل منتج في المتجر يتربط بمنتج مرجعي واحد بس (الأقرب له)،
            # عشان تلاجة واحدة متتحطش قدام 3 تلاجات بأحجام مختلفة
            cands = []
            for p, found in pairs:
                ref = p.get("brand", "") + " " + p["name"]
                for r in found:
                    sim = similar(ref, r.get("brand", "") + " " + r["name"])
                    if sim >= 0.5 and close_price([o["price"] for o in p["offers"]], r["price"]):
                        cands.append((sim, id(p), p, r))
            used_urls, done = set(), set()
            for sim, pid, p, best in sorted(cands, key=lambda c: -c[0]):
                if pid in done or best["url"] in used_urls:
                    continue
                done.add(pid)
                used_urls.add(best["url"])
                if True:
                    p["offers"].append({k: best[k] for k in ("store", "price", "old_price", "url", "in_stock")})
                    if best.get("image") and best["image"] not in p["images"]:
                        p["images"].append(best["image"])
                    print(f"  ↳ {store}: لقيت «{p['name'][:45]}» بـ {best['price']:,}")
            # تشخيص: المنتجات اللي ملقيناهاش في المتجر ده، وإيه أقرب حاجة رجعت
            for p, found in pairs:
                if id(p) in done:
                    continue
                ref = p.get("brand", "") + " " + p["name"]
                near = max(((similar(ref, r.get("brand", "") + " " + r["name"]), r) for r in found),
                           key=lambda x: x[0], default=(0, None))
                mid = sorted(o["price"] for o in p["offers"])[len(p["offers"]) // 2]
                why = (f"أقرب نتيجة «{near[1]['name'][:45]}» تشابه {near[0]:.2f} وسعر {near[1]['price'] / mid:.2f}×"
                       if near[1] else "ولا نتيجة")
                print(f"  ≈ {store}: «{p['name'][:45]}» مش لاقيه ({len(found)} نتيجة؛ {why})")


    paused = {s: 0 for s in SEARCHERS}
    for row in rows:
        q, cat = row["search"].strip(), (row.get("category") or "أخرى").strip()
        for st in SEARCHERS:  # متجر وقفناه؟ نديله فرصة تانية كل 3 كلمات
            if fails[st] >= MAX_FAILS:
                paused[st] += 1
                if paused[st] > 3:
                    paused[st], fails[st] = 0, MAX_FAILS - 1
        results, dead = [], []
        with ThreadPoolExecutor(len(SEARCHERS)) as pool:  # كل متجر في خيط لوحده
            base = dict(zip(SEARCHERS, pool.map(lambda st: run(st, q), SEARCHERS)))
        for store in SEARCHERS:
            found = base[store]
            if found is None:
                dead.append(store)
            else:
                good = [r for r in found if relevant(q, r["name"])]
                results += good
                print(f"✓ {q} / {store}: {len(good)} منتج" + (f" (شلت {len(found) - len(good)} ملهمش علاقة)" if len(good) < len(found) else ""))

        merged = merge(results, cat, q)

        # البحث الموجّه: أهم المنتجات ندوّر عليها بالاسم في المتاجر اللي ملقيناهاش فيها
        live = [s for s in SEARCHERS if fails[s] < MAX_FAILS]
        anchors = sorted(merged, key=lambda p: -len(p["offers"]))[:ANCHORS]
        fill(anchors, live)

        # متجر فشل؟ رجّع آخر أسعاره المعروفة لنفس الكلمة
        for p in old:
            if p.get("search") != q:
                continue
            for o in p.get("offers", []):
                if o["store"] in dead and not any(m["id"] == p["id"] for m in merged):
                    merged.append({**p, "offers": [{**o, "stale": True}]})

        for p in merged:
            if p["id"] not in seen:
                seen.add(p["id"])
                products.append(p)

    # الأقسام المرجعية: ناخد منتجات متجر مرجعي (نون، ولو قافل: كارفور ثم B.TECH ثم 2B)،
    # وكل منتج ندوّر عليه بالاسم في باقي المتاجر
    REF_ORDER = ["noon"]
    browse = [r for r in csv.DictReader(BROWSE.open(encoding="utf-8-sig"))] if BROWSE.exists() else []
    noon_fails, noon_skipped = 0, 0
    for row in browse:
        q, cat = row["search"].strip(), row["category"].strip()
        limit, pages = int(row.get("limit") or 40), int(row.get("pages") or 2)
        strict = (row.get("filter") or "yes").strip().lower() != "no"
        refs, ref_store = [], None
        # عمود stores (اختياري): المتاجر اللي بتبيع القسم ده بس، عشان منضيّعش وقت (مثلاً الملابس مش في B.TECH)
        allowed = {x.strip() for x in (row.get("stores") or "").split("|") if x.strip()} or set(SEARCHERS)
        for store in [s for s in REF_ORDER if s in allowed]:
            if store == "noon":
                if time.time() > DEADLINE:
                    break
                if noon_fails >= 3 and noon_skipped < 5:  # نون قافل؟ نجربه تاني كل 5 أقسام
                    noon_skipped += 1
                    continue
                noon_skipped = 0
                try:
                    for pg in range(1, pages + 1):
                        found = search_noon(q, limit=200, page_no=pg)
                        ok += 1
                        refs += [r for r in found if r["key"] not in {x["key"] for x in refs}]
                        time.sleep(random.uniform(1.5, 3))
                    noon_fails = 0
                except Exception as e:  # noqa: BLE001
                    noon_fails += 1
                    failed.append(f"{q} / noon: {e}")
                    print(f"✗ {q} / noon: {e}", file=sys.stderr)
            if strict:  # شيل النتايج الدخيلة والإكسسوارات
                refs = [r for r in refs if relevant(q, r["name"])]
            if refs:
                ref_store = store
            break
        refs = refs[:limit]
        if not refs:
            # نون قافل: المرجع هو نتايج كل المتاجر التانية مع بعض
            # (ولو القسم واسع زي لعب الأطفال، ندوّر بالكلمات البديلة المحددة)
            alts = [x.strip() for x in (row.get("fallback") or "").split("|") if x.strip()] or [q]
            others = [s for s in SEARCHERS if s != "noon" and s in allowed and fails[s] < MAX_FAILS]
            per = max(3, limit // len(alts)) if len(alts) > 1 else min(limit, 8)
            PER_STORE, saved = per, PER_STORE
            try:
                for aq in alts:
                    with ThreadPoolExecutor(max(1, len(others))) as pool:
                        got = list(pool.map(lambda st: run(st, aq) or [], others))
                    for found in got:
                        refs += [r for r in found if (not strict and len(alts) == 1) or relevant(aq, r["name"])]
            finally:
                PER_STORE = saved
            ref_store = "كل المتاجر" if refs else None
        # مرجع تاني من B.TECH: منتجاته موجودة غالباً في نون وأمازون والمحلات التانية، فبتتقارن أكتر
        extra = []
        if ref_store == "noon" and "btech" in allowed:
            found = run("btech", q) or []
            names = [r["name"] for r in refs]
            for r in found:
                if len(extra) >= SECOND_REF:
                    break
                if (not strict or relevant(q, r["name"])) and \
                        not any(similar(r["name"], n) >= 0.5 for n in names):
                    extra.append(r)
        print(f"✓ قسم «{q}»: {len(refs)} منتج مرجعي من {ref_store or '—'}" + (f" + {len(extra)} من B.TECH" if extra else ""))
        merged = merge(refs + extra, cat, q)
        fill(sorted(merged, key=lambda p: -len(p["offers"]))[:max(limit, ANCHORS) + len(extra)],
             [s for s in SEARCHERS if s in allowed and fails[s] < MAX_FAILS
              and not (s == "noon" and noon_fails >= 3)])
        if not refs:  # كل المتاجر المرجعية قافلة؟ رجّع آخر نسخة من القسم
            merged = [{**p, "offers": [{**o, "stale": True} for o in p["offers"]]}
                      for p in old if p.get("search") == q]
        for p in merged:
            if p["id"] not in seen:
                seen.add(p["id"])
                products.append(p)

    before = len(products)
    products = global_merge(products)
    print(f"الدمج العام: {before - len(products)} منتج اتدمج مع نسخته في متجر تاني")

    refresh_links(products)

    now = datetime.now(timezone.utc)
    for p in products:
        p["seen"] = now.isoformat(timespec="minutes")
    kept = keep_missing(products, old, now)
    products += kept
    print(f"منتجات مختفية اتسابت بآخر سعر (لحد {KEEP_DAYS} يوم): {len(kept)}")

    data = {
        "demo": False,
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "stores": STORES,
        "products": products,
    }
    multi = sum(1 for p in products if len(p["offers"]) > 1)
    print(f"\nتم: {len(products)} منتج ({multi} منهم متقارن في أكتر من متجر). "
          f"{ok} بحث نجح، {len(failed)} فشل.")
    if not products:
        sys.exit("ولا منتج اتجاب. مش هغيّر الموقع.")
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
