"""مؤقت: يجرب خرايط مواقع متاجر مرشحة من سيرفرات GitHub."""
import re, sys, collections
sys.path.insert(0, "scraper")
import discover as d

def locs(u):
    try:
        return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", d.get_xml(u))
    except Exception as e:
        print("  ✗", u, e); return []

def show(name, urls, pat):
    ps = [u for u in urls if re.search(pat, u)]
    print(f"== {name}: {len(urls)} url, {len(ps)} match {pat}")
    shapes = collections.Counter(re.sub(r"[^/]+$", "*", u)[:60] for u in urls)
    print("   shapes", shapes.most_common(8))
    for u in ps[100:103]:
        try: print("   page", u[:100], "→", d.read_page(u))
        except Exception as e: print("   ✗", u[:100], e)

show("halan", locs("https://shop.halan.com/sitemap/active_products"), r"/en/")
mm = locs("https://mobilemasr.com/__sitemap__/en-US.xml"); show("mobilemasr", mm, r"/en/product|/en/p/")
am = locs("https://www.amanstores.com/en/sitemap.xml"); show("aman", am, r"/en/[^/]+/[^/]+/[^/]*\d")
bt = locs("https://www.btech.com/sitemap.xml"); show("btech", bt, r"btech\.com/en/p/")
k = []
for m in [l for l in locs("https://kimostore.net/sitemap.xml") if "products" in l]:
    k += locs(m.replace("&amp;", "&"))
show("kimo", k, r"/products/")
af = []
for m in [l for l in locs("https://alfrensia.com/sitemap_index.xml") if "product-sitemap" in l]:
    af += locs(m)
show("alfrensia", af, r"/en/product/")
tb = []
for m in locs("https://2b.com.eg/en_sitemap.xml"):
    tb += locs(m)
show("2b", tb, r"2b\.com\.eg/en/[a-z0-9-]*\d[a-z0-9-]*\.html$")
x = []
for m in [l for l in locs("https://myxprs.com/sitemap.xml") if "products" in l]:
    x += locs(m.replace("&amp;", "&"))
show("xprs", x, r"/products/")
