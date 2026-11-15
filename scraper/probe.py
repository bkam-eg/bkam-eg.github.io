import sys; sys.path.insert(0, "scraper")
import update_prices as u
T = {"xprs": ["galaxy a56", "sharp refrigerator", "tefal air fryer"], "tradeline": ["iphone 17", "macbook air m4"],
     "ennap": ["iphone 17", "airpods pro"], "elghazawy": ["sharp refrigerator", "tefal air fryer", "samsung tv 55"],
     "mobilemasr": ["galaxy a56", "iphone 17"]}
for st, qs in T.items():
    for q in qs:
        try:
            r = u.SEARCHERS[st](q)
            print(f"== {st} / {q}: {len(r)}")
            for x in r[:4]: print("   ", x["price"], x["name"][:70], x["url"][:90], bool(x["image"]))
        except Exception as e:
            print(f"== {st} / {q}: ERR {e}")
