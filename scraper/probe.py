import re, json
from curl_cffi import requests
s = requests.Session(impersonate="chrome")
def ctx(t, pat, n=2, w=700):
    for m in list(re.finditer(pat, t))[:n]:
        print("   ctx:", re.sub(r"\s+", " ", t[max(0, m.start()-w//3):m.end()+w]))
t = s.get("https://www.raneen.com/en/catalogsearch/result/?q=sharp+refrigerator", timeout=30).text
print("== raneen"); ctx(t, r"product-item-link", 2, 900)
t = s.get("https://cairosales.com/en/search?controller=search&orderby=position&orderway=desc&search_query=samsung+tv+55", timeout=30).text
print("== cairosales tv", re.findall(r'class="product-name" href="([^"]+)"', t)[:8])
ctx(t, r'class="product-name"', 1, 1500)
h = s.get("https://eshop.vodafone.com.eg/en/", timeout=30).text
print("== vodafone main:", s.get("https://eshop.vodafone.com.eg/en/main-LTTLOFKV.js", timeout=30).text[:716])
print("   scripts:", re.findall(r'<script[^>]*src="([^"]+)"', h))
r = s.get("https://www.rayashop.com/en/search?q=galaxy%20a56", timeout=30); t = r.text
chunks = list(dict.fromkeys(re.findall(r'(/_nuxt/[^"\']+\.js)', t)))
print("== raya chunks", len(chunks))
found = set()
for c in chunks[:40]:
    js = s.get("https://www.rayashop.com" + c, timeout=30).text
    for m in re.findall(r'["\'`]([^"\'`]{0,60}(?:search|catalog|products)[^"\'`]{0,80})["\'`]', js):
        if "/" in m and len(found) < 120: found.add(m)
print("   ", sorted(found))
