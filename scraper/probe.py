import re, json
from curl_cffi import requests
s = requests.Session(impersonate="chrome")
def show(label, u, pats=(), n=6, around=None):
    try:
        r = s.get(u, timeout=30); t = r.text
    except Exception as e:
        print("==", label, "ERR", e); return ""
    print("==", label, r.status_code, len(t), u)
    for p in pats:
        print("  ", p, "→", list(dict.fromkeys(re.findall(p, t)))[:n])
    if around:
        m = re.search(around, t)
        if m: print("   ctx:", re.sub(r"\s+", " ", t[max(0, m.start()-600):m.end()+900]))
    return t
# راية
t = show("raya", "https://www.rayashop.com/en/search?q=galaxy%20a56",
         [r'href="(/en/[^"]*a56[^"]*)"', r'https://api-rayashop[^"\' ]+', r'window\.__NUXT__'], around=r"(?i)galaxy a56")
# فودافون: نجيب ملف الـ main ونطلع منه روابط الـ API
h = s.get("https://eshop.vodafone.com.eg/en/", timeout=30).text
for js in re.findall(r'src="([^"]*main-[^"]+\.js)"', h):
    u = js if js.startswith("http") else "https://eshop.vodafone.com.eg/en/" + js
    t = s.get(u, timeout=30).text
    print("== vodafone js", u, len(t))
    print("   urls:", sorted(set(re.findall(r'https?://[a-zA-Z0-9.\-]+(?:/[a-zA-Z0-9_\-/.]*)?', t)))[:60])
    print("   paths:", sorted(set(re.findall(r'["\'`](/?(?:api|services|eshop|product|catalog|search)[a-zA-Z0-9_\-/]*)["\'`]', t)))[:80])
# رانين
t = show("raneen", "https://www.raneen.com/en/catalogsearch/result/?q=sharp+refrigerator",
         [r'(?i)algolia[^"\']{0,80}', r'(?i)klevu[^"\']{0,80}', r'(?i)"applicationId"\s*:\s*"[^"]+"', r'(?i)searchanise', r'href="(https://www\.raneen\.com/en/[^"]*sharp[^"]*)"', r'product-item-link'])
# كايرو سيلز (PrestaShop)
show("cairosales", "https://cairosales.com/en/search?controller=search&orderby=position&orderway=desc&search_query=galaxy+a56",
     [r'class="product-name" href="([^"]+)"', r'class="price product-price">\s*([^<]+)<'])
# حالا
for u in ["https://shop.halan.com/en/search?query=galaxy+a56", "https://shop.halan.com/en/search?keyword=galaxy+a56",
          "https://shop.halan.com/en/search/galaxy%20a56"]:
    show("halan", u, [r'href="(/en/[^"]*A56[^"]*)"', r'"buildId":"[^"]+"'])
