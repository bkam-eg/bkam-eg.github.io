import re, json, gzip
from curl_cffi import requests
s = requests.Session(impersonate="chrome")
SITES = ["https://www.rayashop.com", "https://www.raneen.com", "https://cairosales.com", "https://eshop.vodafone.com.eg",
         "https://zs-eg.com", "https://elghazawy.com", "https://shop.halan.com", "https://mobilemasr.com",
         "https://4umart.net", "https://www.select-egypt.com", "https://myxprs.com", "https://www.istyle.com.eg"]
def get(u):
    r = s.get(u, timeout=40); b = r.content
    if u.endswith(".gz") or b[:2] == b"\x1f\x8b":
        try: b = gzip.decompress(b)
        except Exception: pass
    return r.status_code, b.decode("utf-8", "ignore")
for site in SITES:
    print("=====", site)
    try:
        st, rb = get(site + "/robots.txt")
        maps = re.findall(r"(?im)^sitemap:\s*(\S+)", rb) if st == 200 else []
        print("  robots", st, "sitemaps:", maps[:5], "| disallow search:", bool(re.search(r"(?im)^disallow:.*search", rb)))
        if not maps: maps = [site + "/sitemap.xml"]
        st, sm = get(maps[0])
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm)
        print("  sitemap", st, len(sm), "locs:", len(locs), locs[:4])
        sub = [l for l in locs if re.search(r"(?i)product", l)] or [l for l in locs if l.endswith((".xml", ".gz"))]
        prod = locs
        if sub and sub[0].endswith((".xml", ".gz")) or (locs and locs[0].endswith((".xml", ".gz"))):
            u = (sub or locs)[0]; st, sm2 = get(u)
            prod = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm2)
            print("  sub", u, st, "locs:", len(prod), prod[:3])
        cand = [l for l in prod if not l.endswith((".xml", ".gz")) and re.search(r"(?i)samsung|iphone|sharp|tefal|galaxy|lg-", l)]
        if cand:
            st, pg = get(cand[0])
            ld = re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', pg, re.S)
            info = [x for x in ld if '"Product"' in x or "'Product'" in x]
            pr = re.findall(r'"price"\s*:\s*"?([\d.,]+)', " ".join(info))[:3]
            og = re.findall(r'(?:product:price:amount|itemprop="price")[^>]*content="([^"]+)"', pg)[:2]
            print("  page", cand[0][:110], st, "ld:", len(ld), "Product:", len(info), "price:", pr, "meta:", og)
    except Exception as e:
        print("  ERR", str(e)[:120])
