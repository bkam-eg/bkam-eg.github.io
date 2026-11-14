import re, json
from curl_cffi import requests as http
def get(u):
    r = http.get(u, impersonate="chrome", timeout=30, headers={"Accept-Language": "en-US,en;q=0.9"}); return r.status_code, r.text
def show(k, t, pat, n=2, w=700):
    i = 0
    for m in list(re.finditer(pat, t))[:n]:
        print(f"--- {k} @{m.start()}:", re.sub(r"\s+", " ", t[max(0, m.start()-200): m.start()+w]))
s, t = get("https://www.raneen.com/en/catalogsearch/result/?q=samsung+galaxy")
print("raneen", s, "items:", t.count("product-item-link"), "price-amount:", t.count("data-price-amount"))
show("raneen", t, r"product-item-link", 1)
s, t = get("https://www.raneen.com/en/catalogsearch/result/?q=lego"); print("raneen lego items:", t.count("product-item-link"))
s, t = get("https://www.compumarts.com/search/suggest.json?q=logitech+g502&resources[type]=product&resources[limit]=10")
d = json.loads(t); ps = d["resources"]["results"]["products"]; print("compumarts", len(ps)); print(json.dumps(ps[0], ensure_ascii=False)[:900])
for k, u in {"elbadr": "https://elbadrgroupeg.store/?s=logitech+g502&post_type=product",
             "elghazawy": "https://www.elghazawy.com/en/search?q=logitech+g502",
             "shaheen": "https://shaheenstore.com/search?q=samsung"}.items():
    s, t = get(u)
    print(k, s, len(t), "woo:", t.count("woocommerce-loop-product"), "price:", t.count("woocommerce-Price-amount"))
    show(k, t, r"(?i)g502|galaxy", 2, 900)
for u in ["https://www.shaheenstore.com/products.json?limit=2", "https://elghazawy.com/products.json?limit=1"]:
    try:
        s, t = get(u); print(u, s, t[:300])
    except Exception as e: print(u, e)
