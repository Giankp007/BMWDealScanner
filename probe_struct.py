import truststore; truststore.inject_into_ssl()
import sys, re, json, requests
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "de-CH", "Accept": "text/html"}

def get_next(url):
    r = requests.get(url, headers=H, timeout=25, allow_redirects=True)
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">([\s\S]*?)</script>', r.text)
    return r.status_code, (json.loads(m.group(1)) if m else None), r.text

print("="*60, "\nTUTTI\n", "="*60)
st, d, html = get_next("https://www.tutti.ch/de/q/" + requests.utils.quote("bmw 335i"))
print("status", st)
q = d["props"]["pageProps"]["dehydratedState"]["queries"]
print("num queries:", len(q))
for qi, query in enumerate(q):
    data = query.get("state", {}).get("data", {})
    if not isinstance(data, dict): continue
    lst = data.get("listings")
    print(f" query[{qi}] keys:", list(data.keys())[:8], "| listings type:", type(lst).__name__)
    if isinstance(lst, dict):
        print("   listings dict keys:", list(lst.keys()))
        for ak in ["items","edges","nodes","listings"]:
            if ak in lst and isinstance(lst[ak], list) and lst[ak]:
                arr = lst[ak]
                print(f"   array key '{ak}' len={len(arr)}")
                # find a car listing
                for it in arr:
                    node = it.get("node", it)
                    cat = json.dumps(node.get("primaryCategory") or node.get("category") or "")[:60]
                    if "auto" in cat.lower() or "car" in cat.lower() or "fahrz" in cat.lower():
                        print("   CAR sample:", json.dumps({k:node.get(k) for k in ["listingID","title","formattedPrice","timestamp","postcodeInformation","seoInformation","primaryCategory"]}, ensure_ascii=False)[:500])
                        print("   thumbnail:", json.dumps(node.get("thumbnail"))[:160])
                        break
                else:
                    n0 = arr[0].get("node", arr[0])
                    print("   first item primaryCategory:", json.dumps(n0.get("primaryCategory"))[:120])
                    print("   first item keys:", list(n0.keys()))
                break

print("\n", "="*60, "\nRICARDO\n", "="*60)
for url in ["https://www.ricardo.ch/de/s/bmw%20335i/", "https://www.ricardo.ch/de/c/autos-37711/?query=bmw%20335i"]:
    try:
        r = requests.get(url, headers=H, timeout=25)
        print(url[:55], "->", r.status_code, "len", len(r.text))
        for pat in ["__NEXT_DATA__", "__NUXT__", "__APOLLO_STATE__", "application/json", '"articles"', '"items"', '"price"', '"sellPrice"', 'window.__']:
            if pat in r.text: print("   has", pat)
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)</script>', r.text)
        if m:
            d = json.loads(m.group(1))
            print("   NEXT keys:", list(d.get("props",{}).get("pageProps",{}).keys())[:15])
    except Exception as e:
        print(url[:40], "ERR", repr(e)[:80])
