"""تجربة متاجر جديدة من سيرفرات GitHub (مؤقت)."""
import re, json
from curl_cffi import requests
s = requests.Session(impersonate="chrome")
URLS = {
 "myxprs": "https://myxprs.com/search?type=product&q=galaxy+a56",
 "ennap": "https://ennap.com/search?type=product&q=iphone+17",
 "tradeline": "https://tradelinestores.com/search?type=product&q=iphone+17",
 "mobilemasr": "https://mobilemasr.com/en/search?q=galaxy+a56",
 "elghazawy": "https://elghazawy.com/en/search?q=galaxy+a56",
 "cairosales": "https://cairosales.com/en/search?q=galaxy+a56",
 "zs-api": "https://zs-eg.com/wp-json/wc/store/v1/products?per_page=3&search=sharp+refrigerator",
 "zs-api2": "https://zs-eg.com/wp-json/wc/store/v1/products?per_page=3&search=samsung",
 "raneen": "https://www.raneen.com/en/catalogsearch/result/?q=sharp+refrigerator",
 "halan": "https://shop.halan.com/en/search?q=galaxy+a56",
 "raya": "https://www.rayashop.com/en/search?q=galaxy+a56",
 "vodafone-api": "https://eshop.vodafone.com.eg/en/",
}
for k, u in URLS.items():
    print("=====", k, u)
    try:
        r = s.get(u, timeout=30); t = r.text
    except Exception as e:
        print("ERR", e); continue
    print(r.status_code, len(t))
    print("meta:", "var meta = " in t, "ld+json:", t.count("application/ld+json"), "__NEXT_DATA__:", "__NEXT_DATA__" in t,
          "products/:", len(re.findall(r'href="[^"]*/products?/[^"]+"', t)))
    if t.lstrip().startswith("["):
        for d in json.loads(t)[:3]:
            print("  ", d.get("name"), d.get("prices", {}).get("price"), d.get("prices", {}).get("currency_minor_unit"), d.get("permalink"))
        continue
    links = list(dict.fromkeys(re.findall(r'href="([^"]*(?:/products?/|/p/|\.html)[^"]*)"', t)))[:6]
    print("links:", links)
    m = re.search(r"(?:EGP|ج\.م|LE)\s*[\d,]{4,}|[\d,]{4,}\s*(?:EGP|ج\.م|LE)", t)
    if m:
        a = max(0, m.start() - 1500)
        print("snippet:", re.sub(r"\s+", " ", t[a:m.end() + 300])[-1800:])
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', t)[:8]
    if k == "vodafone-api": print(t[:3000]); print(scripts)
