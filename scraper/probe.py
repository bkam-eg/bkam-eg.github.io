import sys,json
sys.path.insert(0,'scraper')
import update_prices as u
for st in ("dream2000","alsheikh","miami"):
    for q in ("iPhone 17 Pro Max","Samsung Galaxy A56","Sharp air conditioner"):
        try:
            r=u.SEARCHERS[st](q); print("#",st,q,len(r))
            for x in r[:3]: print("   ",x["price"],x["brand"],"|",x["name"][:70],"|",x["url"][:80],"|",bool(x["image"]),x["in_stock"])
        except Exception as e: print("#",st,q,"ERR",e)
