# Big 5 Sporting Goods — Merchandising dashboard generator (workbooks-as-code).
# Usage: python3 build_big5.py <SIGMA_BASE_URL> <TOKEN> <CONNECTION_ID> <FOLDER_ID> [--dry]
# Reshapes SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS into a sporting-goods merchandising model and
# builds a two-tab workbook: a **Storefront** tab (the big5-storefront plugin product-card
# grid + notifications, a comparative KPI row, an AI insight, a category bar + pivot) and an
# **Overview** tab. Register the big5-storefront plugin first (POST /v2/plugins) and export:
#   export BIG5_PLUGIN_ID=<pluginId>
#
# NOTE: targets the CURRENT workbook-spec schema (documentVersion ~600): the spec is wrapped
# in `document` (kind:"workbook") with a FLAT top-level `elements` list; `pages` are {id,name};
# the `layout` XML assigns elements to pages; images use source:{kind:"url",url}; KPIs use
# timeline+periodComparison. Cloned from a fresh GET-back /v2/workbooks/{id}/spec (Accept: json).
import json,sys,os,base64,urllib.request,urllib.error,xml.dom.minidom as _MD
BASE,TOKEN,CONN,FOLDER=sys.argv[1:5]
AICONN="SNOWFLAKE.CORTEX.COMPLETE"
BIG5_PLUGIN=os.environ.get("BIG5_PLUGIN_ID","REPLACE_WITH_YOUR_PLUGIN_ID")
H={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"}
def b64(s): return base64.b64encode(s.encode()).decode()

# ---- formats + brand palette ----
CUR={"kind":"number","formatString":"$.3~s","currencySymbol":"$","decimalSymbol":".","digitGroupingSymbol":",","digitGroupingSize":[3]}
CUR2={"kind":"number","formatString":"$,.2f"}
NUM={"kind":"number","formatString":",.3~s"}
RED="#E4002B"; NAVY="#10233F"; INK="#171717"; SLATE="#6B7280"; W="#FFFFFF"
SCHEME=["#E4002B","#10233F","#1B4DB1","#2E7D46","#7A3FB8","#C2410C","#0E7490","#0369A1"]
CARD={"backgroundColor":"#FFFFFF","borderColor":"#E7E9ED","borderWidth":1,"borderRadius":"round"}
TINT={"backgroundColor":"#FDECEE","borderColor":"#F5C6CE","borderWidth":1,"borderRadius":"round"}

def uri_svg(svg): return "data:image/svg+xml;base64,"+b64(svg)
def img(elid,svg_or_uri,fit="contain"):
    u=svg_or_uri if svg_or_uri.startswith("data:") or svg_or_uri.startswith("http") else uri_svg(svg_or_uri)
    return {"id":elid,"kind":"image","source":{"kind":"url","url":u},"style":{"fit":fit}}
def bgimg(uri,fit="cover"): return {"source":{"kind":"url","url":uri},"style":{"fit":fit}}

HEROBG=uri_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 220" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#FDE7EB"/><stop offset="1" stop-color="#FFFFFF"/></linearGradient></defs><rect width="1600" height="220" fill="url(#g)"/><rect x="0" y="0" width="7" height="220" fill="#E4002B"/></svg>')
def ic(body,col=RED,fill="none",sw=2.2):
    return uri_svg(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{fill}" stroke="{col}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
IC_DOLLAR='<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'
IC_TREND='<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>'
IC_CART='<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>'
IC_BOX='<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>'
IC_PIN='<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>'
IC_ZAP='<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'

logo_svg=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 96" preserveAspectRatio="xMinYMid meet">'
 '<rect x="4" y="20" width="56" height="56" rx="13" fill="#E4002B"/>'
 '<text x="21" y="63" font-family="Arial,sans-serif" font-weight="900" font-style="italic" font-size="42" fill="#FFFFFF">5</text>'
 '<text x="74" y="52" font-family="Arial,sans-serif" font-weight="900" font-size="34" letter-spacing="1" fill="#10233F">BIG 5</text>'
 '<text x="75" y="74" font-family="Arial,sans-serif" font-weight="700" font-size="14" letter-spacing="4" fill="#6B7280">SPORTING GOODS</text></svg>')

MF="Big 5 Sales"
CATS=['Footwear','Team Sports','Camping','Fitness','Apparel','Cycling','Water Sports']
CHAN=['In-Store','Online','Curbside']
CARR="ARRAY_CONSTRUCT("+",".join("'"+c+"'" for c in CATS)+")"
CHARR="ARRAY_CONSTRUCT("+",".join("'"+c+"'" for c in CHAN)+")"
SQL=f"""WITH base AS (
  SELECT ORDER_NUMBER, DATE, DATE_TRUNC('month',DATE) AS USE_MONTH,
    GET({CARR}, MOD(ABS(HASH(PRODUCT_FAMILY)),7))::string AS CATEGORY,
    GET({CHARR}, MOD(ABS(HASH(PRODUCT_LINE)),3))::string AS CHANNEL,
    MOD(ABS(HASH(STORE_STATE)),120) AS STORE,
    QUANTITY*PRICE AS REVENUE, QUANTITY AS UNITS
  FROM SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS
), m AS (SELECT MAX(USE_MONTH) MAXM FROM base)
SELECT base.* FROM base"""
COLS=[("c-date","DATE","Date"),("c-month","USE_MONTH","Month"),
 ("c-cat","CATEGORY","Category"),("c-chan","CHANNEL","Channel"),("c-store","STORE","Store"),
 ("c-rev","REVENUE","Revenue"),("c-units","UNITS","Units")]
sales={"id":"tbl","kind":"table","source":{"connectionId":CONN,"statement":SQL,"kind":"sql"},
 "columns":[{"id":c,"formula":f"[Custom SQL/{s}]","name":d} for c,s,d in COLS],
 "name":MF,"order":[c[0] for c in COLS]}

# ---- products (feeds storefront plugin): 22 sporting-goods SKUs ----
PRODUCTS=[
 ("Trail Runner GTX","Footwear",42,6,4.6,89.99),("Court Classic Low","Footwear",31,18,4.2,64.99),
 ("Everyday Cushion Run","Footwear",58,24,4.7,74.99),("Hike Mid Waterproof","Footwear",12,3,4.4,99.99),
 ("Composite Basketball","Team Sports",26,40,4.5,29.99),("Match Soccer Ball","Team Sports",33,22,4.3,24.99),
 ("Batting Gloves Pro","Team Sports",9,15,4.1,34.99),("4-Person Dome Tent","Camping",7,11,4.6,129.99),
 ("20F Mummy Sleeping Bag","Camping",14,9,4.4,79.99),("2-Burner Camp Stove","Camping",5,2,4.5,59.99),
 ("Double Camp Chair","Camping",21,33,4.2,39.99),("Adjustable Dumbbell 52.5","Fitness",11,4,4.8,199.99),
 ("Yoga Mat 6mm","Fitness",47,52,4.3,24.99),("Resistance Band Set","Fitness",63,71,4.4,19.99),
 ("Kettlebell 35 lb","Fitness",8,13,4.6,44.99),("Dri-Fit Training Tee","Apparel",72,88,4.2,22.99),
 ("Sherpa Fleece Hoodie","Apparel",19,7,4.5,49.99),("Compression Tights","Apparel",28,34,4.1,32.99),
 ('26in Mountain Bike',"Cycling",4,3,4.4,299.99),("Vent Bike Helmet","Cycling",16,20,4.3,39.99),
 ("Kayak Paddle Alloy","Water Sports",6,9,4.2,54.99),("Adult Life Vest","Water Sports",13,17,4.6,44.99)]
def sq(s): return str(s).replace("'","''")
PVALS=",".join(f"('{sq(n)}','{sq(c)}',{so},{av},{ra},{pr})" for n,c,so,av,ra,pr in PRODUCTS)
PSQL=f"SELECT column1 AS PRODUCT, column2 AS CATEGORY, column3 AS SOLD, column4 AS AVAILABLE, column5 AS RATING, column6 AS PRICE FROM (VALUES {PVALS})"
products={"id":"products","kind":"table","name":"Products",
 "source":{"connectionId":CONN,"kind":"sql","statement":PSQL},
 "columns":[{"id":"p-name","formula":"[Custom SQL/PRODUCT]","name":"Product"},
            {"id":"p-cat","formula":"[Custom SQL/CATEGORY]","name":"Category"},
            {"id":"p-sold","formula":"[Custom SQL/SOLD]","name":"Sold","format":NUM},
            {"id":"p-avail","formula":"[Custom SQL/AVAILABLE]","name":"Available","format":NUM},
            {"id":"p-rating","formula":"[Custom SQL/RATING]","name":"Rating"},
            {"id":"p-price","formula":"[Custom SQL/PRICE]","name":"Price","format":CUR2}],
 "order":["p-name","p-cat","p-sold","p-avail","p-rating","p-price"]}

# ---- comparative KPI card (light surface, timeline+periodComparison MoM delta) ----
def kpi(elid,icon,valf,title,fmt,src="tbl"):
    cid=f"c-{elid}"
    cont={"id":cid,"kind":"container","style":dict(CARD)}
    ik=img(f"i-{elid}",icon)
    tcol=f"k-{elid}m"; vcol=f"k-{elid}v"
    kv={"id":f"k-{elid}","kind":"kpi-chart","source":{"elementId":src,"kind":"table"},
        "columns":[{"id":tcol,"formula":f'DateTrunc("month",[{MF}/Date])',"name":"Month"},
                   {"id":vcol,"formula":valf,"name":title,"format":fmt}],
        "value":{"columnId":vcol},"timeline":{"columnId":tcol},"periodComparison":"month",
        "comparison":{"colorGood":"#188A5B","colorBad":"#C11B2E"},
        "layout":{"verticalAnchor":"middle"}}
    lay=(f'  <GridContainer elementId="{cid}" type="grid" gridColumn="{{col}}" gridRow="5 / 13" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="repeat(12,1fr)">\n'
         f'    <LayoutElement elementId="i-{elid}" gridColumn="1 / 3" gridRow="1 / 4"/>\n'
         f'    <LayoutElement elementId="k-{elid}" gridColumn="1 / 13" gridRow="2 / 12"/>\n  </GridContainer>')
    return [cont,ik,kv],lay

KDEFS=[("rev",ic(IC_DOLLAR),f'Sum([{MF}/Revenue])',"Revenue",CUR),
       ("orders",ic(IC_CART),f'Count([{MF}/Revenue])',"Orders",NUM),
       ("aov",ic(IC_TREND),f'Sum([{MF}/Revenue])/Count([{MF}/Revenue])',"Avg Order Value",CUR2),
       ("units",ic(IC_BOX),f'Sum([{MF}/Units])',"Units Sold",NUM)]
kpis=[]; kpilay=[]
for i,(elid,icn,vf,t,fmt) in enumerate(KDEFS):
    e,l=kpi(elid,icn,vf,t,fmt); kpis+=e; kpilay.append(l.replace("{col}",f"{1+i*6} / {1+(i+1)*6}"))

# ---- AI insight ----
ai_body=('{{ Replace(CallText("'+AICONN+'", "CLAUDE-4-SONNET", '
 '"You are a merchandising analyst at Big 5 Sporting Goods, a sporting-goods retailer. In two concise sentences summarize storefront performance given Revenue $" '
 '& Text(Round(Sum(['+MF+'/Revenue])/1000000,1)) & "M, " & Text(Round(Sum(['+MF+'/Units])/1000,0)) '
 '& "K units sold, and an average order value of $" & Text(Round(Sum(['+MF+'/Revenue])/Count(['+MF+'/Revenue]),2)) '
 '& ". Call out the strongest product category and one inventory risk such as stockouts or low stock."), \'"\', \'\') }}')
ai_box={"id":"c-ai","kind":"container","style":dict(TINT)}
ai_ic=img("ai-ic",ic(IC_ZAP,RED,fill=RED))
ai_hd={"id":"ai-hd","kind":"text","body":'**AI insight**'}
ai_sum={"id":"txt-ai","kind":"text","body":ai_body}

# ---- storefront plugin ----
plug_c={"id":"c-plug","kind":"container","style":dict(CARD)}
plug_hd={"id":"plug-hd","kind":"text","body":"**Storefront — live product grid & alerts**"}
plug_el={"id":"storeviz","kind":"plugin","pluginId":BIG5_PLUGIN,"config":{"source":{"kind":"element","elementId":"products"},
  "name":"p-name","category":"p-cat","sold":"p-sold","available":"p-avail","rating":"p-rating","price":"p-price"}}

# ---- category revenue bar + pivot ----
sbar={"id":"sbar","kind":"bar-chart","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"sb-cat","formula":f"[{MF}/Category]","name":"Category"},
            {"id":"sbv","formula":f"Sum([{MF}/Revenue])","name":"Revenue","format":CUR},
            {"id":"sb-catc","formula":f"[{MF}/Category]","name":"Series"}],
 "xAxis":{"columnId":"sb-cat","sort":{"by":"sbv","direction":"descending"}},"yAxis":{"columnIds":["sbv"]},
 "color":{"by":"category","column":"sb-catc","scheme":SCHEME},
 "dataLabel":{"labels":"hidden"},"legend":{"visibility":"hidden"},
 "name":{"text":"Revenue by category","fontWeight":"bold"}}
book={"id":"book","kind":"pivot-table","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"bk-cat","formula":f"[{MF}/Category]","name":"Category"},
            {"id":"bk-rev","formula":f"Sum([{MF}/Revenue])","name":"Revenue","format":CUR},
            {"id":"bk-u","formula":f"Sum([{MF}/Units])","name":"Units","format":NUM},
            {"id":"bk-aov","formula":f"Sum([{MF}/Revenue])/Count([{MF}/Revenue])","name":"Avg order","format":CUR2}],
 "rowsBy":[{"id":"bk-cat"}],"values":["bk-rev","bk-u","bk-aov"],
 "name":{"text":"Category performance","fontWeight":"bold"}}

def header(sfx,title,subtitle):
    c={"id":f"c-hdr{sfx}","kind":"container","style":{"borderRadius":"round","borderColor":"#E7E9ED","borderWidth":1},"backgroundImage":bgimg(HEROBG)}
    lg=img(f"logo{sfx}",logo_svg)
    tt={"id":f"ttl{sfx}","kind":"text","body":f"## {title}"}
    sb={"id":f"sub{sfx}","kind":"text","body":f'<span style="color: {SLATE}">{subtitle}</span>'}
    lay=(f'  <GridContainer elementId="c-hdr{sfx}" type="grid" gridColumn="1 / 25" gridRow="1 / 5" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(6,1fr)">\n'
         f'    <LayoutElement elementId="logo{sfx}" gridColumn="1 / 6" gridRow="2 / 6"/>\n'
         f'    <LayoutElement elementId="ttl{sfx}" gridColumn="7 / 20" gridRow="2 / 4"/>\n'
         f'    <LayoutElement elementId="sub{sfx}" gridColumn="7 / 20" gridRow="4 / 6"/>\n  </GridContainer>')
    return [c,lg,tt,sb],lay

# ============ PAGE 1 — STOREFRONT ============
h1e,h1l=header("1","Merchandising — Storefront","Product performance, availability & alerts · in-store + online")
def page1():
    elems=[sales,products]+h1e+kpis+[ai_box,ai_ic,ai_hd,ai_sum,plug_c,plug_hd,plug_el,sbar,book]
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pg">
{h1l}
{chr(10).join(kpilay)}
  <GridContainer elementId="c-ai" type="grid" gridColumn="1 / 25" gridRow="13 / 17" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(4,1fr)"><LayoutElement elementId="ai-ic" gridColumn="1 / 2" gridRow="1 / 2"/><LayoutElement elementId="ai-hd" gridColumn="2 / 25" gridRow="1 / 2"/><LayoutElement elementId="txt-ai" gridColumn="2 / 25" gridRow="2 / 5"/></GridContainer>
  <GridContainer elementId="c-plug" type="grid" gridColumn="1 / 25" gridRow="17 / 45" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto"><LayoutElement elementId="plug-hd" gridColumn="1 / 25" gridRow="1 / 2"/><LayoutElement elementId="storeviz" gridColumn="1 / 25" gridRow="2 / 28"/></GridContainer>
  <LayoutElement elementId="sbar" gridColumn="1 / 14" gridRow="46 / 64"/>
  <LayoutElement elementId="book" gridColumn="14 / 25" gridRow="46 / 64"/>
</Page>"""
    return elems,lay

# ============ PAGE 2 — OVERVIEW ============
ODEFS=[("orev",ic(IC_DOLLAR),f'Sum([{MF}/Revenue])',"Total Revenue",CUR),
       ("ounits",ic(IC_BOX),f'Sum([{MF}/Units])',"Units Sold",NUM),
       ("ostores",ic(IC_PIN),f'CountDistinct([{MF}/Store])',"Active Stores",NUM)]
O2=[]; O2L=[]
for i,(elid,icn,vf,t,fmt) in enumerate(ODEFS):
    e,l=kpi(elid,icn,vf,t,fmt); O2+=e; O2L.append(l.replace("{col}",f"{1+i*8} / {1+(i+1)*8}"))
ochan={"id":"ochan","kind":"bar-chart","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"oc-cat","formula":f"[{MF}/Category]","name":"Category"},
            {"id":"oc-chan","formula":f"[{MF}/Channel]","name":"Channel"},
            {"id":"oc-rev","formula":f"Sum([{MF}/Revenue])","name":"Revenue","format":CUR}],
 "xAxis":{"columnId":"oc-cat","sort":{"by":"oc-rev","direction":"descending"}},"yAxis":{"columnIds":["oc-rev"]},
 "color":{"by":"category","column":"oc-chan","scheme":SCHEME},"dataLabel":{"labels":"hidden"},
 "legend":{"visibility":"visible"},"name":{"text":"Revenue by category & channel","fontWeight":"bold"}}
otop={"id":"otop","kind":"pivot-table","source":{"elementId":"products","kind":"table"},
 "columns":[{"id":"ot-name","formula":"[Products/Product]","name":"Product"},
            {"id":"ot-cat","formula":"[Products/Category]","name":"Category"},
            {"id":"ot-sold","formula":"Sum([Products/Sold])","name":"Sold","format":NUM},
            {"id":"ot-avail","formula":"Sum([Products/Available])","name":"Available","format":NUM}],
 "rowsBy":[{"id":"ot-cat"},{"id":"ot-name"}],"values":["ot-sold","ot-avail"],
 "name":{"text":"Product sell-through & on-hand","fontWeight":"bold"}}
h2e,h2l=header("2","Merchandising — Overview","Company-wide revenue, units & channel mix")
def page2():
    elems=h2e+O2+[ochan,otop]
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="ov">
{h2l}
{chr(10).join(O2L)}
  <LayoutElement elementId="ochan" gridColumn="1 / 13" gridRow="13 / 33"/>
  <LayoutElement elementId="otop" gridColumn="13 / 25" gridRow="13 / 33"/>
</Page>"""
    return elems,lay

SETTINGS={"theme":{"overrides":{"categoricalScheme":SCHEME,"pageWidth":"full"}},"navigation":{"pageHeader":"disabled"}}

def build():
    p1e,p1l=page1(); p2e,p2l=page2()
    datal=('<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="data">\n'
           '  <Element elementId="tbl" gridColumn="1 / 13" gridRow="1 / 20"/>\n'
           '  <Element elementId="products" gridColumn="13 / 25" gridRow="1 / 20"/>\n</Page>\n')
    lay=('<?xml version="1.0" encoding="utf-8"?>\n'+p1l+p2l+datal).replace("GridContainer","Container").replace("LayoutElement","Element")
    document={"schemaVersion":1,"kind":"workbook",
      "pages":[{"id":"pg","name":"Storefront","pageWidth":"full"},{"id":"ov","name":"Overview","pageWidth":"full"},{"id":"data","name":"Data"}],
      "elements":p1e+p2e,
      "layout":lay,
      "settings":SETTINGS}
    return {"name":"Big 5 Sporting Goods — Merchandising","folderId":FOLDER,"document":document}

def qa(s):
    def _walk(o):
        if isinstance(o,dict):
            for v in o.values(): yield from _walk(v)
        elif isinstance(o,list):
            for v in o: yield from _walk(v)
        elif isinstance(o,str): yield o
    bad=0
    for x in _walk(s):
        if x.startswith("data:image/svg+xml;base64,"):
            try: _MD.parseString(base64.b64decode(x.split(",",1)[1]))
            except Exception as e: bad+=1; print("INVALID SVG:",str(e)[:120])
    return bad

def post(s):
    import re
    r=urllib.request.Request(BASE+"/v2/workbooks/spec",data=json.dumps(s).encode(),headers=H,method="POST")
    resp=urllib.request.urlopen(r,timeout=120).read().decode()
    m=re.search(r'"?workbookId"?\s*[:=]\s*"?([0-9a-f-]{36})',resp)
    wid=m.group(1) if m else None
    url=None
    if wid:
        meta=urllib.request.Request(BASE+f"/v2/workbooks/{wid}",headers={**H,"Accept":"application/json"})
        try: url=json.loads(urllib.request.urlopen(meta,timeout=30).read().decode()).get("url")
        except Exception: pass
    return (wid is not None), url, resp

if __name__=="__main__":
    spec=build()
    if qa(spec): print("ABORT malformed SVG"); sys.exit(1)
    if len(sys.argv)>5 and sys.argv[5]=="--dry":
        json.dump(spec,open("/tmp/big5_spec.json","w"),indent=1); print("dry-run: wrote /tmp/big5_spec.json"); sys.exit(0)
    try:
        ok,url,resp=post(spec); print("POST:","ACCEPTED wid found" if ok else "no wid"); print(resp[:400])
        if url: print("URL:",url)
    except urllib.error.HTTPError as e:
        raw=e.read().decode()
        try: msg=json.loads(raw).get("message","")
        except Exception: msg=raw
        print(f"FAILED: {e.code} {msg[:400]}")
