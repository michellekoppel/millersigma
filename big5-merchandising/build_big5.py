"""
Big 5 Sporting Goods — Merchandising Dashboard generator.

Two pages, styled after the Cold Provisions storefront demo but in Big 5's brand
(royal blue #343A94 + red accent):

  1. STOREFRONT — blue-gradient header + the REAL white Big 5 wordmark, a store-sales
     trend sparkline, a Category dropdown + Product search + a Date filter, and the
     bespoke "Big 5 Storefront Grid" plugin (product cards w/ SVG sporting-goods
     glyphs, rating, sold/available, stock bands + a live notifications rail).
  2. MANAGER — comparative gradient KPI cards (Net Sales / Units / ASP / Margin,
     Current + delta vs Prior Year + sparkline), a live CallText AI insight,
     control-driven charts (grain / color-by / category), a stacked category bar,
     side-by-side pivots, and a merchandising copilot agent.

Data: SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS reshaped into Big 5 categories via custom SQL
(Manager); a curated Big 5 product catalog via VALUES (Storefront grid).

Run:  python3 build_big5.py <BASE_URL> <TOKEN> <CONN_ID> <FOLDER_ID>
Env:  PLUGIN_ID (registered storefront plugin), LOGO_PNG (path to white wordmark png).
"""
import json, sys, os, base64, urllib.request, urllib.error, xml.dom.minidom as _MD

BASE, TOKEN, CONN, FOLDER = sys.argv[1:5]
AICONN = "SNOWFLAKE.CORTEX.COMPLETE"
PLUGIN = os.environ.get("PLUGIN_ID", "REPLACE_WITH_PLUGIN_ID")
H = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}

def b64(s): return base64.b64encode(s.encode()).decode()

# ---------- formats ----------
CUR = {"kind":"number","formatString":"$.3~s","currencySymbol":"$","decimalSymbol":".","digitGroupingSymbol":",","digitGroupingSize":[3]}
CUR2= {"kind":"number","formatString":"$,.2f","currencySymbol":"$","decimalSymbol":".","digitGroupingSymbol":",","digitGroupingSize":[3]}
NUM = {"kind":"number","formatString":",.3~s"}
PCT1= {"kind":"number","formatString":".1%"}
PCT2= {"kind":"number","formatString":"+,.1%"}

# ---------- Big 5 palette ----------
INK="#1A1F36"; SLATE="#8A8F9C"; BLUE="#343A94"; BLUE_D="#1F2570"; RED="#E4002B"; W="#FFFFFF"
CARD={"backgroundColor":"#FFFFFF","borderColor":"#E6E8F0","borderWidth":1,"borderRadius":"round"}
TINT={"backgroundColor":"#EEF1FB","borderColor":"#D8DEF4","borderWidth":1,"borderRadius":"round"}

def grad(a,b):
    return "data:image/svg+xml;base64,"+b64(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs><rect width="400" height="240" fill="url(#g)"/></svg>')
# four blue-family KPI gradients
KG=[grad("#1F2570","#343A94"),grad("#2A2F86","#4854C4"),grad("#12308A","#2E6FB0"),grad("#241C5B","#5B4F9E")]

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def timg(text,size=34,color="#FFFFFF",weight=800,anchor="start"):
    t=esc(text); W_=int(len(text)*size*0.60)+24; Hh=int(size*1.7)
    x=3 if anchor=="start" else (W_//2 if anchor=="middle" else W_-3)
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W_} {Hh}" preserveAspectRatio="xMinYMid meet">'
     f'<text x="{x}" y="{int(Hh*0.70)}" text-anchor="{anchor}" font-family="Inter,Arial,sans-serif" font-weight="{weight}" font-size="{size}" fill="{color}">{t}</text></svg>')
    return "data:image/svg+xml;base64,"+b64(svg)

# real Big 5 white wordmark (png data-uri)
LOGO_PNG=os.environ.get("LOGO_PNG","big5_logo_white.png")
logo_uri="data:image/png;base64,"+base64.b64encode(open(LOGO_PNG,"rb").read()).decode()

HDRBG=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 210" preserveAspectRatio="xMidYMid slice">'
  '<defs>'
  '<linearGradient id="hg" x1="0" y1="0" x2="1" y2="0.35"><stop offset="0" stop-color="#151A5E"/><stop offset="0.5" stop-color="#283093"/><stop offset="1" stop-color="#3A44B4"/></linearGradient>'
  '<radialGradient id="glow" cx="0.85" cy="0.15" r="0.55"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.16"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>'
  '</defs>'
  '<rect width="1600" height="210" fill="url(#hg)"/><rect width="1600" height="210" fill="url(#glow)"/>'
  '<g fill="none" stroke="#AEB7F2" stroke-opacity="0.20" stroke-width="1.4" transform="translate(1380,95)"><circle r="40"/><circle r="76"/><circle r="112"/><line x1="-135" y1="0" x2="135" y2="0"/><line x1="0" y1="-135" x2="0" y2="135"/></g>'
  '</svg>')
HDRBG_URI="data:image/svg+xml;base64,"+b64(HDRBG)

def header(sfx,title,subtitle):
    c={"id":f"c-hdr{sfx}","kind":"container","style":{"borderRadius":"round"},"backgroundImage":{"url":HDRBG_URI,"style":{"fit":"cover"}}}
    lg={"id":f"logo{sfx}","kind":"image","url":logo_uri,"style":{"fit":"scale-down"}}
    tt={"id":f"ttl{sfx}","kind":"image","url":timg(title,32,"#FFFFFF",800,"start"),"style":{"fit":"scale-down"}}
    sb={"id":f"sub{sfx}","kind":"image","url":timg(subtitle,16,"#D7DcFb",500,"start"),"style":{"fit":"scale-down"}}
    lay=(f'  <GridContainer elementId="c-hdr{sfx}" type="grid" gridColumn="1 / 25" gridRow="1 / 5" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(6,1fr)">\n'
         f'    <LayoutElement elementId="logo{sfx}" gridColumn="1 / 6" gridRow="2 / 6"/>\n'
         f'    <LayoutElement elementId="ttl{sfx}" gridColumn="6 / 21" gridRow="2 / 4"/>\n'
         f'    <LayoutElement elementId="sub{sfx}" gridColumn="6 / 21" gridRow="4 / 6"/>\n  </GridContainer>')
    return [c,lg,tt,sb],lay

# ---------- comparative KPI card (Manager) ----------
MF="Big 5"
def _spark(elid,src,trend):
    return {"id":f"ln-{elid}","kind":"line-chart","source":{"elementId":src,"kind":"table"},
        "columns":[{"id":f"ln-{elid}m","formula":f"[{MF}/Month]","name":"Month"},{"id":f"ln-{elid}v","formula":trend,"name":"Trend"}],
        "xAxis":{"columnId":f"ln-{elid}m","format":{"marks":"none","labels":"hidden"}},
        "yAxis":{"columnIds":[f"ln-{elid}v"],"format":{"labels":"hidden","marks":"none","scale":{"type":"linear","zero":False,"hideZeroLine":True}}},
        "name":{"visibility":"hidden"},"legend":{"visibility":"hidden"},"lineAreaStyle":{"interpolation":"monotone"},"style":{"backgroundColor":"transparent","padding":"none"}}
def card(elid,src,title,v1f,v2f,v2lab,fmt,g,trend=None,rowband="5 / 13"):
    cid=f"c-{elid}"
    cont={"id":cid,"kind":"container","style":{"borderRadius":"round"},"backgroundImage":{"url":g,"style":{"fit":"cover"}}}
    els=[cont]; inner=""
    left={"id":f"k-{elid}c","kind":"kpi-chart","source":{"elementId":src,"kind":"table"},
      "columns":[{"id":f"k-{elid}cv","formula":v1f,"name":title,"format":fmt},
                 {"id":f"k-{elid}cc","formula":v2f,"name":"vs "+v2lab,"format":fmt}],
      "value":{"columnId":f"k-{elid}cv","color":W,"fontSize":32},
      "comparisonColumn":{"columnId":f"k-{elid}cc"},
      "comparison":{"display":"delta","colorGood":"#CFEACB","colorBad":"#FFCFC7","fontSize":13},
      "name":{"text":title,"color":W,"fontSize":15},"layout":{"anchor":"middle"},"style":{"backgroundColor":"transparent","padding":"none"}}
    right={"id":f"k-{elid}p","kind":"kpi-chart","source":{"elementId":src,"kind":"table"},
      "columns":[{"id":f"k-{elid}pv","formula":v2f,"name":v2lab,"format":fmt}],
      "value":{"columnId":f"k-{elid}pv","color":W,"fontSize":28},
      "name":{"text":v2lab,"color":W,"fontSize":13},"layout":{"anchor":"middle"},"style":{"backgroundColor":"transparent","padding":"none"}}
    els+=[left,right]
    inner+=(f'    <LayoutElement elementId="k-{elid}c" gridColumn="1 / 7" gridRow="1 / 9"/>\n'
            f'    <LayoutElement elementId="k-{elid}p" gridColumn="7 / 13" gridRow="1 / 9"/>\n')
    if trend:
        els.append(_spark(elid,src,trend)); inner+=f'    <LayoutElement elementId="ln-{elid}" gridColumn="1 / 13" gridRow="9 / 12"/>\n'
    lay=(f'  <GridContainer elementId="{cid}" type="grid" gridColumn="{{col}}" gridRow="{rowband}" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="repeat(12,1fr)">\n'+inner+'  </GridContainer>')
    return els,lay

# ============================================================
#  DATA: Big 5 reshape of BIG_BUYS_POS  (Manager page)
# ============================================================
CATS=['Footwear','Team Sports','Fitness','Camping & Outdoors','Water Sports','Cycling','Fan Gear','Hunting & Fishing']
def arr(xs): return "ARRAY_CONSTRUCT("+",".join("'"+str(x).replace("'","''")+"'" for x in xs)+")"
CATARR=arr(CATS)
SQL=f"""WITH b0 AS (
  SELECT *, MOD(ABS(HASH(PRODUCT_NAME)),8) AS IDX, DATE_TRUNC('month',DATE) AS USE_MONTH
  FROM SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS
  WHERE PRODUCT_NAME IS NOT NULL AND ORDER_NUMBER IS NOT NULL AND STORE_REGION IS NOT NULL
), base AS (
  SELECT ORDER_NUMBER, DATE, USE_MONTH,
    GET({CATARR}, IDX)::string AS CATEGORY,
    INITCAP(STORE_REGION)::string AS REGION,
    STORE_NAME AS STORE,
    QUANTITY AS UNITS,
    QUANTITY*PRICE*0.2 AS NET_SALES,
    QUANTITY*(PRICE-COST)*0.2 AS MARGIN
  FROM b0
), m AS (SELECT MAX(USE_MONTH) MAXM FROM base)
SELECT base.*,
  CASE WHEN USE_MONTH>DATEADD('month',-12,(SELECT MAXM FROM m)) THEN 'Current Period'
       WHEN USE_MONTH>DATEADD('month',-24,(SELECT MAXM FROM m)) THEN 'Prior Year' ELSE NULL END AS PERIOD_NAME
FROM base"""
COLS=[("c-date","DATE","Date"),("c-month","USE_MONTH","Month"),("c-period","PERIOD_NAME","Period Name"),
 ("c-cat","CATEGORY","Category"),("c-reg","REGION","Region"),("c-store","STORE","Store"),
 ("c-order","ORDER_NUMBER","Order"),("c-units","UNITS","Units"),("c-net","NET_SALES","Net Sales"),("c-mar","MARGIN","Margin")]
tbl={"id":"tbl","kind":"table","source":{"connectionId":CONN,"statement":SQL,"kind":"sql"},
 "columns":[{"id":c,"formula":f"[Custom SQL/{s}]","name":d} for c,s,d in COLS],"name":MF,"order":[c[0] for c in COLS],"visibleAsSource":True}

# ============================================================
#  DATA: curated Big 5 product catalog (Storefront grid)
# ============================================================
# (product, category, glyph, price, sold, available, rating, reorder)
CATALOG=[
 ("Trail Runner GTX Shoe","Footwear","shoe",89.99,142,27,4.5,10),
 ("Summit Hiking Boot","Footwear","boot",119.99,98,14,4.7,10),
 ("Court Hi Basketball Shoe","Footwear","bball_shoe",74.99,120,0,4.4,10),
 ("Wave Sport Sandal","Footwear","sandal",34.99,210,52,4.2,12),
 ("Turf Baseball Cleat","Footwear","cleat",59.99,64,6,4.3,10),
 ("Pro Grip Basketball","Team Sports","basketball",29.99,180,33,4.6,12),
 ("All-Weather Football","Team Sports","football",24.99,150,0,4.4,12),
 ("Match Soccer Ball","Team Sports","soccer",22.99,175,41,4.5,12),
 ("Hardball Baseball 12-pk","Team Sports","baseball",19.99,96,58,4.1,12),
 ("Alloy Baseball Bat","Team Sports","bat",79.99,58,12,4.6,8),
 ("Fielder's Baseball Glove","Team Sports","glove",49.99,72,5,4.5,8),
 ("Adjustable Dumbbell 52lb","Fitness","dumbbell",149.99,88,19,4.8,8),
 ("Cast Iron Kettlebell 35lb","Fitness","kettlebell",44.99,110,7,4.5,10),
 ("Premium Yoga Mat","Fitness","yogamat",27.99,240,66,4.4,12),
 ("FlexStride Treadmill","Fitness","treadmill",599.99,22,4,4.3,5),
 ("4-Person Dome Tent","Camping & Outdoors","tent",129.99,54,23,4.5,8),
 ("Mummy Sleeping Bag","Camping & Outdoors","sleepingbag",59.99,77,31,4.4,10),
 ("54qt Wheeled Cooler","Camping & Outdoors","cooler",79.99,63,0,4.6,10),
 ("Folding Camp Chair","Camping & Outdoors","chair",24.99,190,48,4.3,12),
 ("TrailPro 45L Backpack","Camping & Outdoors","backpack",89.99,84,16,4.7,10),
 ("LED Camp Lantern","Camping & Outdoors","lantern",19.99,133,8,4.2,10),
 ("Angler Sit-On Kayak","Water Sports","kayak",349.99,31,9,4.6,6),
 ("Adult Life Vest","Water Sports","lifevest",39.99,120,37,4.4,12),
 ("TrailX Mountain Bike","Cycling","bike",429.99,26,5,4.5,6),
 ("Vent Pro Bike Helmet","Cycling","helmet",49.99,98,29,4.4,10),
 ("Home Team Jersey","Fan Gear","jersey",89.99,140,0,4.5,10),
 ("Fitted Team Cap","Fan Gear","cap",27.99,205,44,4.3,12),
 ("Spinning Fishing Rod Combo","Hunting & Fishing","rod",69.99,59,18,4.4,10),
]
def sq(v):
    return "'"+str(v).replace("'","''")+"'" if isinstance(v,str) else str(v)
CAT_VALUES=",".join("("+",".join(sq(x) for x in row)+")" for row in CATALOG)
CAT_SQL=(f"SELECT column1 AS PRODUCT, column2 AS CATEGORY, column3 AS GLYPH, column4 AS PRICE, "
         f"column5 AS SOLD, column6 AS AVAILABLE, column7 AS RATING, column8 AS REORDER FROM (VALUES {CAT_VALUES})")
# live per-product AI insight (Snowflake Cortex via CallText) — 4 labeled sections the
# plugin modal parses into Overview / Who it's best for / Key features / How it's selling.
AI_FORMULA=('Replace(CallText("SNOWFLAKE.CORTEX.COMPLETE","CLAUDE-4-SONNET",'
 '"You are a Big 5 Sporting Goods merchandising expert. Respond in EXACTLY four labeled sections '
 'separated by three pipe characters |||, with no preamble and no markdown. '
 'Format: OVERVIEW: two short sentences on the product. ||| '
 'BESTFOR: one sentence on which shopper it suits. ||| '
 'FEATURES: one sentence on likely key features or materials. ||| '
 'SELLING: one sentence noting it has sold " & Text([Sold]) & " units with " & Text([Available]) '
 '& " currently in stock. Product: " & [Product] & ", Category: " & [Category] & ", Price $" '
 '& Text([Price]) & ", Rating " & Text([Rating]) & " out of 5."), \'"\', \'\')')
cat_tbl={"id":"cat_tbl","kind":"table","name":"Product Catalog","visibleAsSource":True,
 "source":{"connectionId":CONN,"kind":"sql","statement":CAT_SQL},
 "columns":[{"id":"p-prod","formula":"[Custom SQL/PRODUCT]","name":"Product"},
            {"id":"p-cat","formula":"[Custom SQL/CATEGORY]","name":"Category"},
            {"id":"p-glyph","formula":"[Custom SQL/GLYPH]","name":"Icon"},
            {"id":"p-price","formula":"[Custom SQL/PRICE]","name":"Price","format":CUR2},
            {"id":"p-sold","formula":"[Custom SQL/SOLD]","name":"Sold","format":NUM},
            {"id":"p-avail","formula":"[Custom SQL/AVAILABLE]","name":"Available","format":NUM},
            {"id":"p-rating","formula":"[Custom SQL/RATING]","name":"Rating"},
            {"id":"p-reorder","formula":"[Custom SQL/REORDER]","name":"Reorder point","format":NUM},
            {"id":"p-ai","formula":AI_FORMULA,"name":"AI Insight"}],
 "order":["p-prod","p-cat","p-glyph","p-price","p-sold","p-avail","p-rating","p-reorder","p-ai"]}

# ============================================================
#  PAGE 1 — STOREFRONT
# ============================================================
h1e,h1l=header("1","Store Merchandising","Live storefront — inventory, ratings & stock alerts")
# storefront controls (filter the catalog that feeds the plugin)
ctrl_cat={"kind":"control","controlId":"CatFilter","id":"ctrl-cat","name":"Category","controlType":"list",
  "selectionMode":"multiple","mode":"include","values":[],
  "filters":[{"source":{"kind":"table","elementId":"cat_tbl"},"columnId":"p-cat"}],
  "source":{"kind":"source","source":{"kind":"table","elementId":"cat_tbl"},"columnId":"p-cat"}}
ctrl_search={"kind":"control","controlId":"ProductSearch","id":"ctrl-search","name":"Product search","controlType":"text",
  "mode":"contains","case":"insensitive","includeNulls":"when-no-value-is-selected","showOperators":False,
  "filters":[{"source":{"kind":"table","elementId":"cat_tbl"},"columnId":"p-prod"}],
  "source":{"kind":"source","source":{"kind":"table","elementId":"cat_tbl"},"columnId":"p-prod"}}
ctrl_date={"kind":"control","controlId":"DateFilter","id":"ctrl-date","name":"Date","controlType":"date-range",
  "mode":"between","includeNulls":"always",
  "filters":[{"source":{"kind":"table","elementId":"tbl"},"columnId":"c-date"}]}
tools_c={"id":"c-tools","kind":"container","style":dict(CARD)}
# store-sales trend sparkline (blue bars on a white chip)
trend_c={"id":"c-trend","kind":"container","style":dict(CARD)}
trend_hd={"id":"trend-hd","kind":"text","body":"**Store sales trend** — units sold by month","verticalAlign":"middle","style":{"color":INK}}
trend={"id":"trend","kind":"bar-chart","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"tr-m","formula":f"[{MF}/Month]","name":"Month","format":{"kind":"datetime","formatString":"%b %Y"}},
            {"id":"tr-v","formula":f"Sum([{MF}/Units])","name":"Units","format":NUM},
            {"id":"tr-s","formula":'"Units sold"',"name":"Series"}],
 "xAxis":{"columnId":"tr-m","format":{"labels":"hidden","marks":"none"}},
 "yAxis":{"columnIds":["tr-v"],"format":{"labels":"hidden","marks":"none"}},
 "color":{"by":"category","column":"tr-s","scheme":[BLUE]},
 "legend":{"visibility":"hidden"},"name":{"visibility":"hidden"},"style":{"backgroundColor":"transparent","padding":"none"}}
# the bespoke storefront plugin (product grid + notifications), bound to the catalog
store={"id":"storeviz","kind":"plugin","pluginId":PLUGIN,
 "config":{"source":{"kind":"element","elementId":"cat_tbl"},
   "product":"p-prod","category":"p-cat","glyph":"p-glyph","price":"p-price",
   "sold":"p-sold","available":"p-avail","rating":"p-rating","reorder":"p-reorder","ai":"p-ai"}}
store_c={"id":"c-store","kind":"container","style":dict(CARD)}

def page1():
    elems=[cat_tbl,tbl]+h1e+[tools_c,ctrl_cat,ctrl_search,ctrl_date,trend_c,trend_hd,trend,store_c,store]
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="store">
{h1l}
  <GridContainer elementId="c-tools" type="grid" gridColumn="1 / 25" gridRow="5 / 8" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <LayoutElement elementId="ctrl-cat" gridColumn="1 / 9" gridRow="1 / 4"/>
    <LayoutElement elementId="ctrl-search" gridColumn="9 / 17" gridRow="1 / 4"/>
    <LayoutElement elementId="ctrl-date" gridColumn="17 / 25" gridRow="1 / 4"/>
  </GridContainer>
  <GridContainer elementId="c-trend" type="grid" gridColumn="1 / 25" gridRow="8 / 14" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(6,1fr)">
    <LayoutElement elementId="trend-hd" gridColumn="1 / 25" gridRow="1 / 2"/>
    <LayoutElement elementId="trend" gridColumn="1 / 25" gridRow="2 / 7"/>
  </GridContainer>
  <GridContainer elementId="c-store" type="grid" gridColumn="1 / 25" gridRow="14 / 78" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <LayoutElement elementId="storeviz" gridColumn="1 / 25" gridRow="1 / 90"/>
  </GridContainer>
</Page>"""
    return elems,lay

# ============================================================
#  PAGE 2 — MANAGER
# ============================================================
_P=f'[{MF}/Period Name]="§"'
KDEFS=[("net","NET SALES",f'SumIf([{MF}/Net Sales],{_P})',CUR,f'Sum([{MF}/Net Sales])'),
       ("units","UNITS SOLD",f'SumIf([{MF}/Units],{_P})',NUM,f'Sum([{MF}/Units])'),
       ("asp","AVG SELLING PRICE",f'SumIf([{MF}/Net Sales],{_P})/SumIf([{MF}/Units],{_P})',CUR2,f'Sum([{MF}/Net Sales])/Sum([{MF}/Units])'),
       ("marg","GROSS MARGIN",f'SumIf([{MF}/Margin],{_P})/SumIf([{MF}/Net Sales],{_P})',PCT1,f'Sum([{MF}/Margin])/Sum([{MF}/Net Sales])')]
kpis=[]; kpilay=[]
for i,(elid,t,mf,fmt,tr) in enumerate(KDEFS):
    cur=mf.replace("§","Current Period"); pri=mf.replace("§","Prior Year")
    e,l=card(elid,"tbl",t,cur,pri,"Prior Year",fmt,KG[i],trend=tr,rowband="5 / 13")
    kpis+=e; kpilay.append(l.replace("{col}",f"{1+i*6} / {1+(i+1)*6}"))

ai_body=('{{ Replace(CallText("'+AICONN+'", "CLAUDE-4-SONNET", '
 '"You are a merchandising analyst at Big 5 Sporting Goods (categories: Footwear, Team Sports, Fitness, Camping & Outdoors, Water Sports, Cycling, Fan Gear, Hunting & Fishing). '
 'In two concise sentences summarize store performance given Net Sales of $" '
 '& Text(Round(Sum(['+MF+'/Net Sales])/1000000,1)) & "M, " '
 '& Text(Round(Sum(['+MF+'/Units])/1000,0)) & "K units sold, and a gross margin of " '
 '& Text(Round(Sum(['+MF+'/Margin])/Sum(['+MF+'/Net Sales])*100,1)) & "%. Call out the leading category and any inventory or margin risk."), \'"\', \'\') }}')
ai_box={"id":"c-ai","kind":"container","style":dict(TINT)}
ai_ic={"id":"ai-ic","kind":"image","url":"data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="'+BLUE+'" stroke="'+BLUE+'" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>'),"style":{"fit":"contain"}}
ai_hd={"id":"ai-hd","kind":"text","body":"**AI insight**","verticalAlign":"middle","style":{"color":INK}}
ai_sum={"id":"txt-ai","kind":"text","body":ai_body,"verticalAlign":"middle","style":{"color":"#26304A"}}

grain={"kind":"control","controlId":"DateGrain","id":"ctrl-grain","name":"Date Grain","controlType":"segmented","value":"Month","source":{"kind":"manual","valueType":"text","values":["Quarter","Month","Week"]}}
colorby={"kind":"control","controlId":"ColorBy","id":"ctrl-colorby","name":"Color By","controlType":"segmented","value":"Category","source":{"kind":"manual","valueType":"text","values":["Category","Region"]}}
ctrl_catm={"kind":"control","controlId":"CatM","id":"ctrl-catm","name":"Category","controlType":"list","selectionMode":"multiple","mode":"include","values":[],
  "filters":[{"source":{"kind":"table","elementId":"tbl"},"columnId":"c-cat"}],
  "source":{"kind":"source","source":{"kind":"table","elementId":"tbl"},"columnId":"c-cat"}}
filt_c={"id":"c-filters","kind":"container","style":dict(CARD)}
sbar={"id":"sbar","kind":"bar-chart","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"sbm","formula":f'Switch([DateGrain],"Quarter",DateTrunc("quarter",[{MF}/Date]),"Week",DateTrunc("week",[{MF}/Date]),DateTrunc("month",[{MF}/Date]))',"name":"Period","format":{"kind":"datetime","formatString":"%b %Y"}},
            {"id":"sbv","formula":f"Sum([{MF}/Net Sales])","name":"Net Sales","format":CUR},
            {"id":"sbc","formula":f'Switch([ColorBy],"Category",[{MF}/Category],"Region",[{MF}/Region])',"name":"Series"}],
 "xAxis":{"columnId":"sbm"},"yAxis":{"columnIds":["sbv"]},
 "color":{"by":"category","column":"sbc","scheme":["#343A94","#4854C4","#2E6FB0","#5B4F9E","#8A92E0","#E4002B","#00A3A3","#F0872E"]},"stacking":"stacked",
 "dataLabel":{"labels":"hidden"},"legend":{"visibility":"visible"},"name":{"text":"Net sales by period & category","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}
mix={"id":"mix","kind":"pivot-table","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"mx-cat","formula":f"[{MF}/Category]","name":"Category"},
            {"id":"mx-net","formula":f"Sum([{MF}/Net Sales])","name":"Net Sales","format":CUR},
            {"id":"mx-units","formula":f"Sum([{MF}/Units])","name":"Units","format":NUM},
            {"id":"mx-marg","formula":f"Sum([{MF}/Margin])/Sum([{MF}/Net Sales])","name":"Margin","format":PCT1}],
 "rowsBy":[{"id":"mx-cat"}],"values":["mx-net","mx-units","mx-marg"],
 "conditionalFormats":[{"type":"single","columnIds":["mx-net"],"condition":"IsNotNull","style":{"backgroundColor":"#EAEDFB"}}],
 "name":{"text":"Category mix","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}
reg={"id":"reg","kind":"pivot-table","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"rg-cat","formula":f"[{MF}/Category]","name":"Category"},{"id":"rg-reg","formula":f"[{MF}/Region]","name":"Region"},{"id":"rg-net","formula":f"Sum([{MF}/Net Sales])","name":"Net Sales","format":CUR}],
 "rowsBy":[{"id":"rg-cat"}],"columnsBy":[{"id":"rg-reg"}],"values":["rg-net"],
 "conditionalFormats":[{"type":"single","columnIds":["rg-net"],"condition":"IsNotNull","style":{"backgroundColor":"#EAEDFB"}}],
 "name":{"text":"Net sales — Category x Region","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}

AGENT={"id":"ag-merch","name":"Big 5 Merchandising Copilot",
 "instructions":("You are a merchandising analyst for Big 5 Sporting Goods (categories: Footwear, Team Sports, Fitness, Camping & Outdoors, Water Sports, Cycling, Fan Gear, Hunting & Fishing; multiple store regions). "
   "Answer questions about net sales, units sold, average selling price, gross margin by category and region, period-over-period trends, and inventory/stockout risk. Be concise and quantitative."),
 "dataSources":[{"kind":"table","elementId":"tbl"}]}
def rail(with_agent):
    c={"id":"c-chat","kind":"container","style":dict(CARD)}
    ric={"id":"chat-ic","kind":"image","url":"data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="'+BLUE+'" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>'),"style":{"fit":"contain"}}
    hdr={"id":"chat-hdr","kind":"text","body":"**Ask Big 5 AI**","verticalAlign":"middle","style":{"color":INK}}
    if with_agent: inner={"id":"chat","kind":"chat","agentId":"ag-merch"}
    else: inner={"id":"chat","kind":"text","verticalAlign":"middle","style":{"color":"#26304A","backgroundColor":"#EEF1FB"},"body":"**Ask AI for insights**\n\n- Which category drives the most net sales?\n- Where is margin strongest by region?\n- Which items are at stockout risk?"}
    lay=('  <GridContainer elementId="c-chat" type="grid" gridColumn="18 / 25" gridRow="20 / 58" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="auto">\n'
         '    <LayoutElement elementId="chat-ic" gridColumn="1 / 3" gridRow="1 / 2"/>\n'
         '    <LayoutElement elementId="chat-hdr" gridColumn="3 / 13" gridRow="1 / 2"/>\n'
         '    <LayoutElement elementId="chat" gridColumn="1 / 13" gridRow="2 / 40"/>\n  </GridContainer>')
    return [c,ric,hdr,inner],lay

h2e,h2l=header("2","Merchandising Manager","Net sales, units, price & margin across categories and regions")
def page2(with_agent):
    re,rl=rail(with_agent)
    elems=[h2e[0]]+h2e[1:]+kpis+[ai_box,ai_ic,ai_hd,ai_sum,filt_c,grain,colorby,ctrl_catm,sbar,mix,reg]+re
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="manager">
{h2l}
{chr(10).join(kpilay)}
  <GridContainer elementId="c-ai" type="grid" gridColumn="1 / 25" gridRow="13 / 17" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(4,1fr)"><LayoutElement elementId="ai-ic" gridColumn="1 / 2" gridRow="1 / 2"/><LayoutElement elementId="ai-hd" gridColumn="2 / 25" gridRow="1 / 2"/><LayoutElement elementId="txt-ai" gridColumn="2 / 25" gridRow="2 / 5"/></GridContainer>
  <GridContainer elementId="c-filters" type="grid" gridColumn="1 / 25" gridRow="17 / 20" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <LayoutElement elementId="ctrl-grain" gridColumn="1 / 9" gridRow="1 / 4"/><LayoutElement elementId="ctrl-colorby" gridColumn="9 / 17" gridRow="1 / 4"/><LayoutElement elementId="ctrl-catm" gridColumn="17 / 25" gridRow="1 / 4"/>
  </GridContainer>
  <LayoutElement elementId="sbar" gridColumn="1 / 18" gridRow="20 / 40"/>
  <LayoutElement elementId="mix" gridColumn="1 / 13" gridRow="40 / 58"/>
  <LayoutElement elementId="reg" gridColumn="13 / 18" gridRow="40 / 58"/>
{rl}
</Page>"""
    return elems,lay

theme={"colors":{"text":INK,"highlight":BLUE,"success":"#2E7D46","warning":"#C77700","danger":RED,"darkMode":"hidden"},
 "colorOverrides":{"backgroundCanvas":"#FFFFFF","canvasBackground":"#F5F6FB"},
 "categoricalScheme":["#FFFFFF","#343A94","#4854C4","#2E6FB0","#5B4F9E","#8A92E0","#E4002B","#00A3A3"],
 "fonts":{"textFont":"Inter","dataFont":"Inter"},"pageWidth":"full","tableStyles":{"preset":"presentation","cellSpacing":"small"}}

def normalize(o):
    """Rewrite image url / backgroundImage to the CURRENT schema:
       image  -> source:{kind:url, url:...}
       container.backgroundImage -> {source:{kind:url,url:...}, style:...}"""
    if isinstance(o,dict):
        if o.get("kind")=="image" and "url" in o and "source" not in o:
            o["source"]={"kind":"url","url":o.pop("url")}
        bg=o.get("backgroundImage")
        if isinstance(bg,dict) and "url" in bg and "source" not in bg:
            bg["source"]={"kind":"url","url":bg.pop("url")}
        for v in o.values(): normalize(v)
    elif isinstance(o,list):
        for v in o: normalize(v)
    return o

def build(mode):
    wa=mode!="none"
    p1e,p1l=page1(); p2e,p2l=page2(wa)
    s={"name":"Big 5 Sporting Goods — Merchandising Dashboard","folderId":FOLDER,"schemaVersion":1,
       "pages":[{"id":"store","name":"Storefront","elements":p1e},{"id":"manager","name":"Manager","elements":p2e}],
       "layout":'<?xml version="1.0" encoding="utf-8"?>\n'+p1l+p2l,"themeOverrides":theme}
    if wa: s["agents"]=[AGENT]
    return normalize(s)

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
    r=urllib.request.Request(BASE+"/v2/workbooks/spec",data=json.dumps(s).encode(),headers=H,method="POST")
    resp=urllib.request.urlopen(r,timeout=120).read().decode()
    wid=[l.split()[-1] for l in resp.splitlines() if "workbookId" in l]
    url=json.loads(urllib.request.urlopen(urllib.request.Request(BASE+f"/v2/workbooks/{wid[0]}",headers=H),timeout=30).read().decode()).get("url") if wid else None
    return ("success: true" in resp), url, resp, (wid[0] if wid else None)

if __name__=="__main__":
    done=False
    for mode in ["basic","none"]:
        spec=build(mode)
        if qa(spec): print("ABORT malformed SVG"); sys.exit(1)
        try:
            ok,url,resp,wid=post(spec); print(f"POST (agent mode={mode}):","ACCEPTED" if ok else resp[:400])
            if ok: print("workbookId:",wid); print("URL:",url); done=True; break
        except urllib.error.HTTPError as e:
            raw=e.read().decode()
            try: msg=json.loads(raw).get("message","")
            except Exception: msg=raw
            print(f"  mode={mode} failed: {e.code} {msg[:300]}")
    if not done: print("ALL MODES FAILED")
