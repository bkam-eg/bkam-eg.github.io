import sys, random; sys.path.insert(0, "scraper")
import discover as d
for st in d.SITEMAP_STORES:
    try:
        u = d.product_urls(st)
        print(f"== {st}: {len(u)}", random.sample(u, min(5, len(u))))
        if u:
            for x in random.sample(u, min(2, len(u))):
                print("   read:", x[:90], d.read_page(x))
    except Exception as e:
        print("== ", st, "ERR", e)
d.BUDGET = 15 * 60
d.main(test=True)
