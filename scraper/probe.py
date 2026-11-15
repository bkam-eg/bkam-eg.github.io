import re,sys
sys.path.insert(0,'scraper')
from update_prices import fetch
page=fetch("https://btech.com/en/s?q=Samsung+Smart+TV+55").replace('\\"','"')
for m in list(re.finditer(r'\{"variant_id":"[^"]+","product_id":"[^"]+"',page))[:3]:
    c=page[m.start():m.start()+2500]
    print('#####',c)
    vid=re.search(r'"variant_id":"([^"]+)"',c).group(1); pid=re.search(r'"product_id":"([^"]+)"',c).group(1)
    for k in (vid,pid):
        print('ctx',k,[page[i.start()-120:i.start()+60] for i in re.finditer(re.escape(k),page)][:4])
