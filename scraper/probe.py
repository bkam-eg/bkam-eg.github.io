import sys; sys.path.insert(0, "scraper")
import update_prices as u
for st, q in [("compumarts", "Logitech G502"), ("compumarts", "PS5 Slim"), ("elbadr", "Logitech G502"), ("elbadr", "Samsung Galaxy A56"),
              ("2b", "Apple iPhone 17 Pro"), ("2b", "LEGO Classic"), ("carrefour", "LEGO Classic")]:
    try:
        r = u.SEARCHERS[st](q)
        print(f"{st} «{q}»: {len(r)}")
        for x in r[:4]: print("   ", x["name"][:60], x["price"], x["old_price"], x["in_stock"], x["image"][:50], x["url"][:60])
    except Exception as e:
        print(st, q, "ERR", e)
