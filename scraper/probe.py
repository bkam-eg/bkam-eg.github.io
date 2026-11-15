"""تجربة متاجر جديدة من سيرفرات GitHub (مؤقت)."""
import re, json
from curl_cffi import requests
Q = "galaxy a56"
SITES = ["https://egypt.sharafdg.com", "https://shop.halan.com", "https://myxprs.com", "https://mobilemasr.com",
         "https://zs-eg.com", "https://elghazawy.com", "https://4umart.net", "https://ennap.com",
         "https://www.elavocatomobile.net", "https://www.raneen.com", "https://www.rayashop.com",
         "https://cairosales.com", "https://eshop.vodafone.com.eg", "https://www.gamesworldegypt.com",
         "https://mob4me.com", "https://www.select-egypt.com", "https://www.istyle.com.eg", "https://tradelinestores.com"]
PATHS = ["/search?type=product&q=", "/en/search?type=product&q=", "/wp-json/wc/store/v1/products?per_page=3&search=",
         "/?post_type=product&s=", "/catalogsearch/result/?q=", "/search?q=", "/en/search?q="]
s = requests.Session(impersonate="chrome")
for site in SITES:
    print("=====", site)
    try:
        r = s.get(site, timeout=25)
        t = r.text
        gen = [k for k in ("Shopify", "woocommerce", "Magento", "wp-content", "__NEXT_DATA__", "salla", "zid", "cf-chl", "captcha", "Vercel")
               if k.lower() in t.lower()]
        print("home", r.status_code, len(t), r.url, gen)
    except Exception as e:
        print("home ERR", e); continue
    for p in PATHS:
        try:
            r = s.get(site + p + Q.replace(" ", "+"), timeout=25)
            t = r.text
            hits = len(re.findall(r"a56", t, re.I))
            price = re.findall(r"(?:EGP|ج\.م|LE)\s*[\d,]{4,}|[\d,]{4,}\s*(?:EGP|ج\.م|LE)", t)[:3]
            js = t.lstrip().startswith("[")
            print(f"  {r.status_code} {len(t):>7} a56×{hits:<3} json={js} {price} {p}")
            if js and r.status_code == 200:
                try:
                    d = json.loads(t)
                    if d: print("    ", d[0].get("name"), d[0].get("prices", {}).get("price"), d[0].get("permalink"))
                except Exception: pass
        except Exception as e:
            print("  ERR", p, str(e)[:80])
