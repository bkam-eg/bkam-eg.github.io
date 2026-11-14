import re
from curl_cffi import requests as http
C = {
 "raneen": "https://www.raneen.com/en/catalogsearch/result/?q=iphone",
 "elaraby": "https://elarabygroup.com/en/catalogsearch/result?q=iphone",
 "dream2000": "https://dream2000.com/search/suggest.json?q=iphone&resources[type]=product",
 "tradeline": "https://www.tradelinestores.com/en/search?q=iphone",
 "cairosales": "https://www.cairosales.com/en/search?controller=search&s=iphone",
 "compumarts": "https://www.compumarts.com/search/suggest.json?q=logitech&resources[type]=product",
 "sigma": "https://www.sigma-computer.com/en/search?q=logitech",
 "elbadr": "https://elbadrgroupeg.store/?s=logitech&post_type=product",
 "mobileshop": "https://mobileshop.eg/en/search?q=iphone",
 "hyperone": "https://www.hyperone.com.eg/search?q=iphone",
 "toysrus": "https://www.toysrus.com.eg/en/search?q=lego",
 "hamleys": "https://www.hamleys.com.eg/search?q=lego",
 "kidzapp_toyz": "https://www.toyzone-eg.com/search?q=lego",
 "babyshop": "https://www.babyshopstores.com/eg/en/search?q=lego",
 "mumzworld": "https://www.mumzworld.com/eg-en/search?q=lego",
 "select": "https://www.select.com.eg/search?q=iphone",
 "sharafdg": "https://egypt.sharafdg.com/?q=iphone",
 "elghazawy": "https://www.elghazawy.com/en/search?q=logitech",
 "dubaiphone": "https://dubaiphone.net/search?q=iphone",
 "shaheen": "https://shaheenstore.com/search?q=iphone",
 "jumia": "https://www.jumia.com.eg/catalog/?q=iphone",
 "kanbkam": "https://www.kanbkam.com/eg/en/search?q=iphone",
 "smsm": "https://www.smsm.com.eg/search?q=iphone",
 "2b_short": "https://2b.com.eg/en/catalogsearch/result/?q=Apple+iPhone+17+Pro",
 "2b_long": "https://2b.com.eg/en/catalogsearch/result/?q=Apple+iPhone+17+Pro+Max+256GB+Deep",
}
MARK = {"shopify": "cdn.shopify", "magento": "Magento", "woo": "woocommerce", "next": "__NEXT_DATA__",
        "nextrsc": "self.__next_f", "nuxt": "__NUXT__", "presta": "prestashop", "salla": "salla",
        "cf": "Just a moment", "captcha": "captcha", "zid": "zid.store"}
for k, u in C.items():
    try:
        r = http.get(u, impersonate="chrome", timeout=30, headers={"Accept-Language": "en-US,en;q=0.9"})
        t = r.text
        m = [n for n, s in MARK.items() if s.lower() in t.lower()]
        hits = len(re.findall(r"iphone|logitech|lego", t, re.I))
        prices = len(re.findall(r"(EGP|ج\.م|LE)\s*[\d,]{3,}|[\d,]{3,}\s*(EGP|ج\.م)", t))
        title = re.search(r"<title>([^<]{0,60})", t)
        print(f"{k:12} {r.status_code} len={len(t):7} hits={hits:4} prices={prices:3} {m} {r.url[:60]} | {title.group(1).strip() if title else ''}")
        if k.startswith("2b_"):
            print("   2b items:", t.count('class="product-item-link"'))
    except Exception as e:
        print(f"{k:12} ERR {str(e)[:90]}")
