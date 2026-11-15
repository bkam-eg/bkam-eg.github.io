import json,re,sys
sys.path.insert(0,'scraper')
from update_prices import fetch
P=json.load(open('products.json'))['products']
seen={}
for p in P:
    for o in p['offers']:
        if o['store'] not in seen and o.get('url'): seen[o['store']]=o['url']
for st,u in seen.items():
    print('=====',st,u[:120])
    try:
        h=fetch(u)
    except Exception as e:
        print('ERR',e); continue
    print('len',len(h))
    for kw in ['ld+json','Specification','specification','__NEXT_DATA__','additional-attributes','product-attribute','"specs"','highlights','"attributes"','spec-table','data-th']:
        i=h.find(kw)
        if i>=0: print('--',kw,'@',i, re.sub(r'\s+',' ',h[i:i+700]))
