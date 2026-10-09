import os, re, glob, json, collections
R=r"D:\PycharmProjects\MyQuant-backtrader"; X=r"D:\exports"
srcs=[]
srcs.append(("repo stock_pool", os.path.join(R,"stock_pool"), "csv"))
srcs.append(("repo stock_pool_xls", os.path.join(R,"stock_pool_xls"), "xls"))
for d in sorted(glob.glob(os.path.join(X,"strategy9_pool_*"))): srcs.append((os.path.basename(d), d, "csv"))
srcs.append(("s10_tr_bb1000", os.path.join(X,"s10_tr_bb1000_20260825_20260909"), "csv"))
srcs.append(("v11 seed30_export_b pool", os.path.join(X,r"v11_slice_d_20260921\seed30_export_b\pool"), "csv"))
srcs.append(("topk signals pool", os.path.join(X,r"topk_s1_cap_cli_host_20261001\signals\pool"), "csv"))
rx=re.compile(r'^\s*=?"?([0-9]{6})(?![0-9])(?:\.(SH|SZ|BJ))?', re.I)
def wind(c,s):
    if s: return f"{c}.{s.upper()}"
    if c[0]=="6": return c+".SH"
    if c[0] in "03": return c+".SZ"
    if c[0] in "489": return c+".BJ"
    return None
allc=collections.OrderedDict(); stats=[]; bad=set()
for name,p,kind in srcs:
    if not os.path.isdir(p): stats.append(dict(source=name,path=p,missing=True)); continue
    fs=sorted(glob.glob(os.path.join(p,"*."+kind)))
    if name=="repo stock_pool": fs=[f for f in fs if "20251023"<=os.path.basename(f)[:8]<="20260909"]
    cs=set()
    for f in fs:
        raw=open(f,"rb").read()
        for enc in ("utf-8-sig","gbk","latin1"):
            try: t=raw.decode(enc); break
            except: pass
        for i,l in enumerate(t.splitlines()):
            m=rx.match(l)
            if not m: continue
            w=wind(m.group(1),m.group(2))
            if w: cs.add(w)
            else: bad.add(m.group(1))
    for c in sorted(cs): allc.setdefault(c,[]).append(name)
    stats.append(dict(source=name,path=p,files=len(fs),unique=len(cs)))
codes=sorted(allc)
open("universe.txt","w").write("\n".join(codes)+"\n")
json.dump(dict(stats=stats,total=len(codes),unmapped=sorted(bad),by_exch=collections.Counter(c[-2:] for c in codes)),open(r"work\universe_stats.json","w"),indent=1)
for s in stats: print(s)
print("total",len(codes),collections.Counter(c[-2:] for c in codes),"unmapped",sorted(bad)[:10])
