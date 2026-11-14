import re, json
from curl_cffi import requests as http
def get(u):
    r = http.get(u, impersonate="chrome", timeout=30, headers={"Accept-Language": "en-US,en;q=0.9"}); return r.status_code, r.text
s, t = get("https://www.compumarts.com/search/suggest.json?q=logitech+g502&resources[type]=product&resources[limit]=10")
for p in json.loads(t)["resources"]["results"]["products"][:3]:
    p.pop("body", None); print("CM", json.dumps(p, ensure_ascii=False)[:700])
s, t = get("https://elbadrgroupeg.store/?s=logitech+g502&post_type=product")
i = t.find('class="product-img'); print("EB", re.sub(r"\s+", " ", t[i-300:i+3500]))
print("EB count", t.count('class="product-img'))
s, t = get("https://www.elghazawy.com/en/search?q=logitech+g502")
for m in list(re.finditer(r"(?i)G502", t))[2:5]:
    print("EG", re.sub(r"\s+", " ", t[m.start()-1500:m.start()+1500]))
