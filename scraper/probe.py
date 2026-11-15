import json,re,sys
sys.path.insert(0,'scraper')
from update_prices import fetch
P=json.load(open('products.json'))['products']
u={}
for p in P:
    for o in p['offers']:
        if o['store'] in('carrefour','compumarts') and o['store'] not in u: u[o['store']]=o['url']
h=fetch(u['carrefour'])
for m in re.finditer('Specification',h): print('C@',m.start(),repr(h[m.start()-80:m.start()+1500]))
h=fetch(u['compumarts'])
for m in list(re.finditer('dark-spec-table|<table',h))[:6]: print('M@',m.start(),repr(h[m.start()-50:m.start()+900]))
