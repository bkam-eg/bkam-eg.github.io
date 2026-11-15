import re,sys,json
from curl_cffi import requests as http
H={"Accept-Language":"en-US,en;q=0.9"}
for b in ["https://dream2000.com","https://alsheikhstores.com"]:
    for u in [b+"/en/search?q=iphone+17+pro&type=product", b+"/en/search?q=iphone+17+pro&type=product&view=json", b+"/en/search?type=product&q=iphone+17+pro&section_id=main-search"]:
        r=http.get(u,impersonate="chrome",timeout=30,headers=H); t=r.text
        print("#####",u,r.status_code,len(t))
        m=re.search(r'var meta = (\{.*?\});',t)
        if m: print("META",m.group(1)[:1500])
        for i in [x.start() for x in re.finditer(r'href="(/en)?/products/',t)][:2]:
            print("CARD",re.sub(r'\s+',' ',t[i-300:i+1500]))
        j=t.find('"@type":"Product"'); 
        if j>0: print("LD",t[j-200:j+600])
