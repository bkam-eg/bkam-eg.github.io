import re,sys,json
sys.path.insert(0,'scraper')
from curl_cffi import requests as http
H={"Accept-Language":"en-US,en;q=0.9,ar;q=0.8"}
def get(u):
    try:
        r=http.get(u,impersonate="chrome",timeout=30,headers=H,allow_redirects=True)
        return r.status_code,r.text,str(r.url)
    except Exception as e: return 0,str(e),u
sites={"miami":"https://miamicenters.com","dream":"https://dream2000.com","dubai":"https://www.dubaiphone.net","sheikh":"https://alsheikhstores.com"}
paths=["/","/search/suggest.json?q=iphone&resources[type]=product","/products.json?limit=2","/catalogsearch/result/?q=iphone","/?s=iphone&post_type=product","/wp-json/wc/store/v1/products?search=iphone&per_page=3","/search?q=iphone","/en/search?q=iphone","/ar/search?q=iphone","/api/search?q=iphone"]
for k,b in sites.items():
    print("#########",k)
    for p in paths:
        s,t,u=get(b+p)
        plat=[n for n,pat in [("shopify","cdn.shopify|Shopify.theme"),("magento","Magento|mage/"),("woo","woocommerce|wp-content"),("salla","salla"),("zid","zid.store|zid-"),("next","__NEXT_DATA__|_next/"),("nuxt","__NUXT"),("cf","Just a moment|cf-chl"),("vercel","Vercel Security Checkpoint")] if re.search(pat,t[:200000],re.I)]
        prices=len(re.findall(r'(?:EGP|ج\.م|جنيه|LE)\s?[\d,]{3,}|[\d,]{3,}\s?(?:EGP|ج\.م|جنيه|LE)',t))
        print(f"{p[:55]:55} {s} len={len(t)} final={u[:60]} plat={plat} prices={prices} iphone={t.lower().count('iphone')}")
        if p.startswith(("/search/suggest","/products.json","/wp-json")) and s==200: print("   ",t[:400].replace("\n"," "))
