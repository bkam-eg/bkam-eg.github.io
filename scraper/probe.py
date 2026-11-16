"""مؤقت: يجرب خرايط مواقع متاجر مرشحة من سيرفرات GitHub."""
import re, sys, json
sys.path.insert(0, "scraper")
import update_prices as up
import discover as d

SITES = ["https://shop.halan.com", "https://cairosales.com", "https://www.mobilemasr.com", "https://myxprs.com",
         "https://www.hyperone.com.eg", "https://kimostore.net", "https://egyptlaptop.com", "https://www.select-egypt.com",
         "https://www.elarabygroup.com", "https://www.2b.com.eg", "https://www.compumarts.com", "https://dream2000.com",
         "https://www.tradelinestores.com", "https://www.amanstores.com", "https://www.samsung.com/eg",
         "https://shop.lg.com", "https://www.mi-egypt.com", "https://www.alfrensia.com", "https://www.elbadrgroupeg.store",
         "https://www.homzmart.com", "https://www.oscarstores.com", "https://www.spinneys-egypt.com",
         "https://www.fresh.com.eg", "https://www.tornado.com.eg", "https://www.sigma-computer.com",
         "https://www.badr.com.eg", "https://www.istyle-eg.com", "https://www.ozone.com.eg", "https://www.smartbuyeg.com",
         "https://www.eshtery.com", "https://www.extra.com", "https://egyptstore.net", "https://www.btech.com"]

for base in SITES:
    try:
        r = up.http.get(base + "/robots.txt", impersonate="chrome", timeout=30)
        maps = re.findall(r"(?im)^sitemap:\s*(\S+)", r.text) if r.status_code == 200 else []
        print(f"== {base} robots {r.status_code} maps={maps[:4]}")
        if not maps:
            maps = [base + "/sitemap.xml", base + "/sitemap_index.xml"]
        for m in maps[:2]:
            try:
                x = d.get_xml(m)
            except Exception as e:
                print("   ✗", m, e); continue
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", x)
            print(f"   {m}: {len(locs)} loc; {locs[:6]}")
            subs = [l for l in locs if ".xml" in l]
            prod = [l for l in subs if "product" in l.lower()] or subs
            if prod:
                try:
                    y = d.get_xml(prod[0]); pl = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", y)
                    print(f"   sub {prod[0]}: {len(pl)}; {pl[1:4]}")
                    cands = [u for u in pl if ".xml" not in u and not re.search(r"\.(jpg|png|webp)", u)]
                except Exception as e:
                    print("   ✗ sub", e); cands = []
            else:
                cands = [u for u in locs if re.search(r"\d", u.rsplit('/',1)[-1])]
            for u in cands[5:7]:
                try:
                    print("   page", u[:90], "→", d.read_page(u))
                except Exception as e:
                    print("   ✗ page", u[:90], e)
            break
    except Exception as e:
        print(f"== {base} ✗ {e}")
