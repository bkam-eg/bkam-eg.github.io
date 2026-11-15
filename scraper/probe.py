import re
from curl_cffi import requests
s = requests.Session(impersonate="chrome")
r = s.get("https://www.rayashop.com/en/search/galaxy%20a56", timeout=30); t = r.text
print("== raya path", r.status_code, len(t), "a56:", len(re.findall(r"(?i)a56", t)))
for m in list(re.finditer(r'(?i)galaxy[ -]a56', t))[:3]:
    print("   ctx:", re.sub(r"\s+", " ", t[max(0, m.start()-400):m.end()+600]))
print("   prices:", re.findall(r'"(?:price|final_price|special_price)"\s*:\s*"?([\d.]+)', t)[:10])
# فودافون: نمشي على الـ chunks وندوّر على أي API
base = "https://eshop.vodafone.com.eg/en/"
todo, seen, hosts, paths = ["main-LTTLOFKV.js"], set(), set(), set()
while todo and len(seen) < 60:
    c = todo.pop(0)
    if c in seen: continue
    seen.add(c)
    try: js = s.get(base + c, timeout=30).text
    except Exception: continue
    todo += [x for x in re.findall(r'\./(chunk-[A-Z0-9]+\.js)', js) if x not in seen]
    hosts |= set(re.findall(r'https://[a-z0-9.\-]+vodafone[a-z0-9.\-]*', js))
    paths |= set(m for m in re.findall(r'["\'`](/?[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-/]*(?:search|product|catalog|listing|item)[a-zA-Z0-9_\-/]*)["\'`]', js))
print("== vodafone chunks", len(seen)); print("   hosts:", sorted(hosts)); print("   paths:", sorted(paths)[:80])
