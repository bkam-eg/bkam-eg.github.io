import re
from curl_cffi import requests as http
for u in ["https://elbadrgroupeg.store/index.php?route=product/search&search=logitech%20g502",
          "https://elbadrgroupeg.store/index.php?route=product/search&search=g502",
          "https://elbadrgroupeg.store/search?search=logitech%20g502"]:
    r = http.get(u, impersonate="chrome", timeout=30)
    t = r.text
    print(u, r.status_code, len(t), r.url[:90], "layouts:", t.count("product-layout"), "names:", len(re.findall(r'<div class="name"><a', t)))
    for m in re.findall(r'<div class="name"><a href="[^"]+">([^<]+)</a>', t)[:4]: print("   ", m[:70])
    i = t.find('<div class="price">'); print("   P:", re.sub(r"\s+", " ", t[i:i+300]))
