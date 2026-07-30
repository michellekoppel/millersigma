"""
Big 5 Sporting Goods — Merchandising Command Center. Cloned from build_company_command_center.py
(the canonical current-standard generator) and reskinned for a sporting-goods MERCHANDISING POV.

PRODUCES 2 pages:
 (1) Merchandising Command Center — navy->red gradient header + white Big 5 wordmark +
     4 COMPARATIVE KPI cards (Net Sales / Gross Margin $ / Gross Margin % / Units, each with a
     native Delta-vs-Prior-Year badge + prior value + sparkline), a live CallText AI insight,
     Color-By/Date-Grain/Category filters, a stacked net-sales bar, the BESPOKE Category
     Productivity Matrix plugin (treemap: tile size = net sales, color = gross margin %) bound to
     its own aggregate element, two side-by-side pivots (category mix + category x region), analyst agent.
 (2) Assortment & Margin Planner — linked input-table drivers (Sales Growth %, Margin Rate pts,
     Markdown %) -> projected sales/margin/contribution KPIs + create/submit/approve, a planning
     copilot agent with an insert-rows tool.

Data: SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS reshaped via custom SQL into sporting-goods merchandising
(real PRICE/COST -> honest margin % and AUR; PRODUCT_FAMILY/LINE/BRAND/TIER/STATE -> category,
department, brand, price tier, western region). MULT scales POS to a believable ~$1B chain.

Run: PLUGIN_ID=<id> python3 build_big5.py <BASE> <TOKEN> <CONN> <FOLDER> [BASE_ROWS_JSON]
BASE_ROWS_JSON (optional): path to a JSON list of {category,sales,margin,units} used as the
page-2 planning base so it ties out to page-1 actuals (produced by the export-and-calibrate step).
"""
import json,sys,os,base64,urllib.request,urllib.error,xml.dom.minidom as _MD
BASE,TOKEN,CONN,FOLDER=sys.argv[1:5]
BASE_ROWS_JSON=sys.argv[5] if len(sys.argv)>5 else None
AICONN="SNOWFLAKE.CORTEX.COMPLETE"; MATRIX=os.environ.get("PLUGIN_ID","REPLACE_WITH_YOUR_PLUGIN_ID")
MULT=float(os.environ.get("MULT","0.4"))  # scales POS to a believable ~$1B western chain
H={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"}
def b64(s): return base64.b64encode(s.encode()).decode()
def bgimg(uri,fit="cover"): return {"source":{"kind":"url","url":uri},"style":{"fit":fit}}  # current backgroundImage shape
CUR={"kind":"number","formatString":"$.3~s","currencySymbol":"$","decimalSymbol":".","digitGroupingSymbol":",","digitGroupingSize":[3]}
NUM={"kind":"number","formatString":",.3~s"}; AURFMT={"kind":"number","formatString":"$,.2f"}
PCT2={"kind":"number","formatString":"+,.1%"}; PCT1={"kind":"number","formatString":".1%"}
INK="#0A2240"; SLATE="#5B6B7B"; RED="#E4002B"; NAVY="#0A2240"; STEEL="#1B4A7A"; W="#FFFFFF"
CARD={"backgroundColor":"#FFFFFF","borderColor":"#E3E8EE","borderWidth":1,"borderRadius":"round"}
TINT={"backgroundColor":"#EAF1F8","borderColor":"#CFE0F0","borderWidth":1,"borderRadius":"round"}
def grad(a,b):
    return "data:image/svg+xml;base64,"+b64(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs><rect width="400" height="240" fill="url(#g)"/></svg>')
KG=[grad("#0A2240","#1B4A7A"),grad("#A4001F","#E4002B"),grad("#0A2240","#7A0E1F"),grad("#1B4A7A","#3B7DB8")]
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def timg(text,size=34,color="#FFFFFF",weight=800,anchor="start"):
    t=esc(text); W_=int(len(text)*size*0.60)+24; Hh=int(size*1.7)
    x=3 if anchor=="start" else (W_//2 if anchor=="middle" else W_-3)
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W_} {Hh}" preserveAspectRatio="xMinYMid meet">'
     f'<text x="{x}" y="{int(Hh*0.70)}" text-anchor="{anchor}" font-family="Inter,Arial,sans-serif" font-weight="{weight}" font-size="{size}" fill="{color}">{t}</text></svg>')
    return "data:image/svg+xml;base64,"+b64(svg)
# Big 5 white wordmark (clean typographic fallback — never a garbled image-model logo).
def logo_svg():
    svg=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 96" preserveAspectRatio="xMinYMid meet">'
      '<g fill="#FFFFFF">'
      '<text x="0" y="58" font-family="Inter,Arial,sans-serif" font-weight="900" font-size="62" letter-spacing="-1">BIG</text>'
      '<circle cx="214" cy="38" r="34" fill="#FFFFFF"/>'
      '<text x="214" y="60" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-weight="900" font-size="54" fill="#E4002B">5</text>'
      '<text x="2" y="88" font-family="Inter,Arial,sans-serif" font-weight="700" font-size="17" letter-spacing="6">SPORTING GOODS</text>'
      '</g></svg>')
    return "data:image/svg+xml;base64,"+b64(svg)
logo_uri=logo_svg()
HDRBG=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 210" preserveAspectRatio="xMidYMid slice">'
  '<defs>'
  '<linearGradient id="hg" x1="0" y1="0" x2="1" y2="0.35"><stop offset="0" stop-color="#0A2240"/><stop offset="0.55" stop-color="#8A0F1E"/><stop offset="1" stop-color="#E4002B"/></linearGradient>'
  '<radialGradient id="glow" cx="0.84" cy="0.16" r="0.55"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.16"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>'
  '</defs>'
  '<rect width="1600" height="210" fill="url(#hg)"/><rect width="1600" height="210" fill="url(#glow)"/>'
  '<g fill="none" stroke="#FFD9CF" stroke-opacity="0.20" stroke-width="1.4" transform="translate(1380,90)"><circle r="30"/><circle r="58"/><circle r="86"/><circle r="114"/></g>'
  '</svg>')
HDRBG_URI="data:image/svg+xml;base64,"+b64(HDRBG)
def header(sfx,title,subtitle):
    c={"id":f"c-hdr{sfx}","kind":"container","style":{"borderRadius":"round"},"backgroundImage":bgimg(HDRBG_URI)}
    lg={"id":f"logo{sfx}","kind":"image","source":{"kind":"url","url":logo_uri},"style":{"fit":"scale-down"}}
    tt={"id":f"ttl{sfx}","kind":"image","source":{"kind":"url","url":timg(title,34,"#FFFFFF",800,"middle")},"style":{"fit":"scale-down"}}
    sb={"id":f"sub{sfx}","kind":"image","source":{"kind":"url","url":timg(subtitle,17,"#FFE1D8",500,"middle")},"style":{"fit":"scale-down"}}
    lay=(f'  <GridContainer elementId="c-hdr{sfx}" type="grid" gridColumn="1 / 25" gridRow="1 / 5" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(6,1fr)">\n'
         f'    <LayoutElement elementId="logo{sfx}" gridColumn="1 / 8" gridRow="2 / 6"/>\n'
         f'    <LayoutElement elementId="ttl{sfx}" gridColumn="8 / 21" gridRow="2 / 4"/>\n'
         f'    <LayoutElement elementId="sub{sfx}" gridColumn="8 / 21" gridRow="4 / 6"/>\n  </GridContainer>')
    return [c,lg,tt,sb],lay
def _spark(elid,src,trend):
    return {"id":f"ln-{elid}","kind":"line-chart","source":{"elementId":src,"kind":"table"},
        "columns":[{"id":f"ln-{elid}m","formula":f"[{MF}/Month]","name":"Month"},{"id":f"ln-{elid}v","formula":trend,"name":"Trend"}],
        "xAxis":{"columnId":f"ln-{elid}m","format":{"marks":"none","labels":"hidden"}},
        "yAxis":{"columnIds":[f"ln-{elid}v"],"format":{"labels":"hidden","marks":"none","scale":{"type":"linear","zero":False,"hideZeroLine":True}}},
        "name":{"visibility":"hidden"},"legend":{"visibility":"hidden"},"lineAreaStyle":{"interpolation":"monotone"},"style":{"backgroundColor":"transparent","padding":"none"}}
def card(elid,src,title,v1f,v2f,v2lab,fmt,g,trend=None,rowband="5 / 13"):
    cid=f"c-{elid}"
    cont={"id":cid,"kind":"container","style":{"borderRadius":"round"},"backgroundImage":bgimg(g)}
    els=[cont]; inner=""
    if v2f:
        left={"id":f"k-{elid}c","kind":"kpi-chart","source":{"elementId":src,"kind":"table"},
          "columns":[{"id":f"k-{elid}cv","formula":v1f,"name":title,"format":fmt},
                     {"id":f"k-{elid}cc","formula":v2f,"name":"vs "+v2lab,"format":fmt}],
          "value":{"columnId":f"k-{elid}cv","color":W,"fontSize":32},
          "comparisonColumn":{"columnId":f"k-{elid}cc"},
          "comparison":{"display":"delta","colorGood":"#CDEBB8","colorBad":"#FFCFC7","fontSize":13},
          "name":{"text":title,"color":W,"fontSize":15},"layout":{"anchor":"middle"},"style":{"backgroundColor":"transparent","padding":"none"}}
        right={"id":f"k-{elid}p","kind":"kpi-chart","source":{"elementId":src,"kind":"table"},
          "columns":[{"id":f"k-{elid}pv","formula":v2f,"name":v2lab,"format":fmt}],
          "value":{"columnId":f"k-{elid}pv","color":W,"fontSize":28},
          "name":{"text":v2lab,"color":W,"fontSize":13},"layout":{"anchor":"middle"},"style":{"backgroundColor":"transparent","padding":"none"}}
        els+=[left,right]
        inner+=(f'    <LayoutElement elementId="k-{elid}c" gridColumn="1 / 7" gridRow="1 / 9"/>\n'
                f'    <LayoutElement elementId="k-{elid}p" gridColumn="7 / 13" gridRow="1 / 9"/>\n')
    else:
        left={"id":f"k-{elid}c","kind":"kpi-chart","source":{"elementId":src,"kind":"table"},
          "columns":[{"id":f"k-{elid}cv","formula":v1f,"name":title,"format":fmt}],
          "value":{"columnId":f"k-{elid}cv","color":W,"fontSize":40},
          "name":{"text":title,"color":W,"fontSize":16},"layout":{"anchor":"middle"},"style":{"backgroundColor":"transparent","padding":"none"}}
        els.append(left); inner+=f'    <LayoutElement elementId="k-{elid}c" gridColumn="1 / 13" gridRow="1 / 9"/>\n'
    if trend:
        els.append(_spark(elid,src,trend)); inner+=f'    <LayoutElement elementId="ln-{elid}" gridColumn="1 / 13" gridRow="9 / 12"/>\n'
    lay=(f'  <GridContainer elementId="{cid}" type="grid" gridColumn="{{col}}" gridRow="{rowband}" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="repeat(12,1fr)">\n'+inner+'  </GridContainer>')
    return els,lay

# ============ PAGE 1 DATA (sporting-goods merchandising reshape) ============
MF="Big 5"
CATS=['Athletic Footwear','Apparel','Team Sports','Fitness & Exercise','Camping & Outdoors','Hunting & Fishing','Cycling & Skate','Winter Sports','Water Sports','Game Room & Rec']
DEPTS=['Running','Basketball','Training','Outerwear','Backpacks & Bags','Balls & Gear','Weights & Benches','Footwear Accessories']
BRANDS=['Nike','adidas','Under Armour','New Balance','ASICS','Wilson','Spalding','Coleman','Columbia','Everlast']
TIERS=['Good','Better','Best']
REGIONS=['Pacific','Southwest','Mountain','Northwest']
def arr(xs): return "ARRAY_CONSTRUCT("+",".join("'"+str(x).replace("'","''")+"'" for x in xs)+")"
CATARR=arr(CATS); DEPTARR=arr(DEPTS); BRANDARR=arr(BRANDS); TIERARR=arr(TIERS); REGARR=arr(REGIONS)
# Weighted category mix (row share, sums to 100) -> a realistic descending sporting-goods assortment.
# Assigned off high-cardinality PRODUCT_KEY so every category fills (low-card PRODUCT_FAMILY left buckets empty).
CATWTS=[22,18,14,11,10,9,6,4,3,3]
def cat_case(col="PRODUCT_KEY"):
    r=f"MOD(ABS(HASH({col})),100)"; cum=0; expr="CASE "
    for i,(c,w) in enumerate(zip(CATS,CATWTS)):
        cum+=w
        if i<len(CATS)-1: expr+=f"WHEN {r}<{cum} THEN '{c}' "
    expr+=f"ELSE '{CATS[-1]}' END"; return expr
CATCASE=cat_case()
# Characteristic gross-margin rate per category (realistic sporting-goods spread; softlines rich, hardlines thin).
# Keyed to the SAME PRODUCT_KEY buckets as the category, so category<->margin stay perfectly aligned.
CATMARGINS=[0.34,0.47,0.40,0.30,0.38,0.27,0.33,0.44,0.36,0.49]
def marg_case(col="PRODUCT_KEY"):
    r=f"MOD(ABS(HASH({col})),100)"; cum=0; expr="CASE "
    for i,(w,mg) in enumerate(zip(CATWTS,CATMARGINS)):
        cum+=w
        if i<len(CATS)-1: expr+=f"WHEN {r}<{cum} THEN {mg} "
    expr+=f"ELSE {CATMARGINS[-1]} END"; return expr
MARGCASE=marg_case()
SQL=f"""WITH b0 AS (
  SELECT *, ABS(HASH(PRODUCT_FAMILY)) AS HF, DATE_TRUNC('month',DATE) AS USE_MONTH FROM SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS
  WHERE PRODUCT_FAMILY IS NOT NULL AND PRODUCT_LINE IS NOT NULL AND STORE_STATE IS NOT NULL
    AND ORDER_NUMBER IS NOT NULL AND QUANTITY IS NOT NULL AND PRICE IS NOT NULL AND COST IS NOT NULL
), base AS (
  SELECT ORDER_NUMBER, DATE, USE_MONTH,
    {CATCASE} AS CATEGORY,
    GET({DEPTARR}, MOD(ABS(HASH(PRODUCT_LINE)),8))::string AS DEPARTMENT,
    GET({BRANDARR}, MOD(ABS(HASH(BRAND)),10))::string AS BRAND_NAME,
    GET({TIERARR}, LEAST(2, MOD(ABS(HASH(SKU_NUMBER)),5)))::string AS PRICE_TIER,
    GET({REGARR}, MOD(ABS(HASH(STORE_STATE)),4))::string AS REGION,
    QUANTITY AS UNITS,
    QUANTITY*PRICE*{MULT} AS NET_SALES,
    QUANTITY*PRICE*{MULT}*({MARGCASE}) AS MARGIN
  FROM b0
), m AS (SELECT MAX(USE_MONTH) MAXM FROM base)
SELECT base.*, CASE WHEN USE_MONTH>DATEADD('month',-12,(SELECT MAXM FROM m)) THEN 'Current Period'
  WHEN USE_MONTH>DATEADD('month',-24,(SELECT MAXM FROM m)) THEN 'Prior Year' ELSE NULL END AS PERIOD_NAME
FROM base"""
COLS=[("c-date","DATE","Date"),("c-month","USE_MONTH","Month"),("c-period","PERIOD_NAME","Period Name"),
 ("c-cat","CATEGORY","Category"),("c-dept","DEPARTMENT","Department"),("c-brand","BRAND_NAME","Brand"),
 ("c-tier","PRICE_TIER","Price Tier"),("c-reg","REGION","Region"),
 ("c-order","ORDER_NUMBER","Order"),("c-units","UNITS","Units"),("c-sales","NET_SALES","Net Sales"),("c-margin","MARGIN","Margin")]
tbl={"id":"tbl","kind":"table","source":{"connectionId":CONN,"statement":SQL,"kind":"sql"},
 "columns":[{"id":c,"formula":f"[Custom SQL/{s}]","name":d} for c,s,d in COLS],"name":MF,"order":[c[0] for c in COLS],"visibleAsSource":True}
# category-productivity-matrix source: current-period aggregate, one row per category
CATSQL=f"""WITH b0 AS (
  SELECT *, ABS(HASH(PRODUCT_FAMILY)) AS HF, DATE_TRUNC('month',DATE) AS USE_MONTH FROM SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS
  WHERE PRODUCT_FAMILY IS NOT NULL AND QUANTITY IS NOT NULL AND PRICE IS NOT NULL AND COST IS NOT NULL
), base AS (
  SELECT {CATCASE} AS CATEGORY, USE_MONTH,
    QUANTITY AS UNITS, QUANTITY*PRICE*{MULT} AS NET_SALES, QUANTITY*PRICE*{MULT}*({MARGCASE}) AS MARGIN FROM b0
), m AS (SELECT MAX(USE_MONTH) MAXM FROM base)
SELECT CATEGORY, SUM(NET_SALES) AS NET_SALES, SUM(UNITS) AS UNITS,
  DIV0(SUM(MARGIN),SUM(NET_SALES)) AS MARGIN_PCT
FROM base WHERE USE_MONTH>DATEADD('month',-12,(SELECT MAXM FROM m)) GROUP BY CATEGORY"""
catagg={"id":"catagg","kind":"table","name":"Category Aggregate","visibleAsSource":True,
 "source":{"connectionId":CONN,"kind":"sql","statement":CATSQL},
 "columns":[{"id":"ca-cat","formula":"[Custom SQL/CATEGORY]","name":"Category"},
            {"id":"ca-sales","formula":"[Custom SQL/NET_SALES]","name":"Net Sales","format":CUR},
            {"id":"ca-units","formula":"[Custom SQL/UNITS]","name":"Units","format":NUM},
            {"id":"ca-gm","formula":"[Custom SQL/MARGIN_PCT]","name":"Gross Margin %","format":PCT1}],
 "order":["ca-cat","ca-sales","ca-units","ca-gm"]}

_P='[{0}/Period Name]="§"'.format(MF)
KDEFS=[("sales","NET SALES",f'SumIf([{MF}/Net Sales],{_P})',CUR,f'Sum([{MF}/Net Sales])'),
       ("gm","GROSS MARGIN $",f'SumIf([{MF}/Margin],{_P})',CUR,f'Sum([{MF}/Margin])'),
       ("gmp","GROSS MARGIN %",f'SumIf([{MF}/Margin],{_P})/SumIf([{MF}/Net Sales],{_P})',PCT1,f'Sum([{MF}/Margin])/Sum([{MF}/Net Sales])'),
       ("units","UNITS SOLD",f'SumIf([{MF}/Units],{_P})',NUM,f'Sum([{MF}/Units])')]
kpis=[]; kpilay=[]
for i,(elid,t,mf,fmt,tr) in enumerate(KDEFS):
    cur=mf.replace("§","Current Period"); pri=mf.replace("§","Prior Year")
    e,l=card(elid,"tbl",t,cur,pri,"Prior Year",fmt,KG[i],trend=tr,rowband="5 / 13"); kpis+=e; kpilay.append(l.replace("{col}",f"{1+i*6} / {1+(i+1)*6}"))

ai_body=('{{ Replace(CallText("'+AICONN+'", "CLAUDE-4-SONNET", '
 '"You are a merchandising analyst at Big 5 Sporting Goods, a western-US sporting-goods retailer '
 '(categories: Athletic Footwear, Apparel, Team Sports, Fitness, Camping, Hunting & Fishing, Cycling, Winter/Water Sports, Game Room). '
 'In two concise sentences summarize the assortment given trailing-12-month Net Sales of $" '
 '& Text(Round(SumIf(['+MF+'/Net Sales],['+MF+'/Period Name]="Current Period")/1000000,1)) & "M, Gross Margin of $" '
 '& Text(Round(SumIf(['+MF+'/Margin],['+MF+'/Period Name]="Current Period")/1000000,1)) & "M, and a blended gross-margin rate of " '
 '& Text(Round(SumIf(['+MF+'/Margin],['+MF+'/Period Name]="Current Period")/SumIf(['+MF+'/Net Sales],['+MF+'/Period Name]="Current Period")*100,1)) '
 '& "%. Call out the highest-productivity category and any thin-margin category that needs a markdown or assortment review."), \'"\', \'\') }}')
ai_box={"id":"c-ai","kind":"container","style":dict(TINT)}
ai_ic={"id":"ai-ic","kind":"image","source":{"kind":"url","url":"data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="'+RED+'" stroke="'+RED+'" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>')},"style":{"fit":"contain"}}
ai_hd={"id":"ai-hd","kind":"text","body":"**AI insight**","verticalAlign":"middle","style":{"color":INK}}
ai_sum={"id":"txt-ai","kind":"text","body":ai_body,"verticalAlign":"middle","style":{"color":"#22364C"}}
grain={"kind":"control","controlId":"DateGrain","id":"ctrl-grain","name":"Date Grain","controlType":"segmented","value":"Month","source":{"kind":"manual","valueType":"text","values":["Quarter","Month","Week","Day"]}}
colorby={"kind":"control","controlId":"ColorBy","id":"ctrl-colorby","name":"Color By","controlType":"segmented","value":"Category","source":{"kind":"manual","valueType":"text","values":["Category","Brand","Price Tier","Region"]}}
ctrl_cat={"kind":"control","controlId":"CatF","id":"ctrl-catf","name":"Category","controlType":"list","selectionMode":"multiple","mode":"include","values":[],"filters":[{"source":{"kind":"table","elementId":"tbl"},"columnId":"c-cat"}],"source":{"kind":"source","source":{"kind":"table","elementId":"tbl"},"columnId":"c-cat"}}
filt_c={"id":"c-filters","kind":"container","style":dict(CARD)}
sbar={"id":"sbar","kind":"bar-chart","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"sbm","formula":f'Switch([DateGrain],"Quarter",DateTrunc("quarter",[{MF}/Date]),"Week",DateTrunc("week",[{MF}/Date]),"Day",DateTrunc("day",[{MF}/Date]),DateTrunc("month",[{MF}/Date]))',"name":"Period","format":{"kind":"datetime","formatString":"%b %d, %Y"}},
            {"id":"sbv","formula":f"Sum([{MF}/Net Sales])","name":"Net Sales","format":CUR},
            {"id":"sbc","formula":f'Switch([ColorBy],"Category",[{MF}/Category],"Brand",[{MF}/Brand],"Price Tier",[{MF}/Price Tier],"Region",[{MF}/Region])',"name":"Series"},
            {"id":"sb-cat","formula":f"[{MF}/Category]","name":"Category"},{"id":"sb-brand","formula":f"[{MF}/Brand]","name":"Brand"},{"id":"sb-tier","formula":f"[{MF}/Price Tier]","name":"Price Tier"},{"id":"sb-reg","formula":f"[{MF}/Region]","name":"Region"}],
 "xAxis":{"columnId":"sbm"},"yAxis":{"columnIds":["sbv"]},"color":{"by":"category","column":"sbc","scheme":["#E4002B","#0A2240","#1B4A7A","#3B7DB8","#F0872E","#8A0F1E","#5B6B7B","#15803D","#2E6FB0","#94A3B8"]},"stacking":"stacked",
 "dataLabel":{"labels":"hidden"},"legend":{"visibility":"visible"},"name":{"text":"Net sales by period & category","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}
matrix_c={"id":"c-matrix","kind":"container","style":dict(CARD)}
matrix_hd={"id":"matrix-hd","kind":"text","body":"**Category productivity matrix** — tile size = net sales, color = gross-margin %","verticalAlign":"middle","style":{"color":INK}}
matrix_el={"id":"matrixviz","kind":"plugin","pluginId":MATRIX,"config":{"source":{"kind":"element","elementId":"catagg"},"category":"ca-cat","sales":"ca-sales","margin":"ca-gm","units":"ca-units"}}
heat={"id":"heat","kind":"pivot-table","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"hm","formula":f"[{MF}/Category]","name":"Category"},{"id":"hp","formula":f"[{MF}/Region]","name":"Region"},{"id":"hv","formula":f"Sum([{MF}/Net Sales])","name":"Net Sales","format":CUR}],
 "rowsBy":[{"id":"hm"}],"columnsBy":[{"id":"hp"}],"values":["hv"],
 "conditionalFormats":[{"type":"single","columnIds":["hv"],"condition":"IsNotNull","style":{"backgroundColor":"#E7EEF6"}}],
 "name":{"text":"Net sales — Category x Region","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}
book={"id":"book","kind":"pivot-table","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"bk-cat","formula":f"[{MF}/Category]","name":"Category"},
            {"id":"bk-sales","formula":f"Sum([{MF}/Net Sales])","name":"Net Sales","format":CUR},
            {"id":"bk-gm","formula":f"Sum([{MF}/Margin])","name":"Margin $","format":CUR},
            {"id":"bk-gmp","formula":f"Sum([{MF}/Margin])/Sum([{MF}/Net Sales])","name":"Margin %","format":PCT1},
            {"id":"bk-aur","formula":f"Sum([{MF}/Net Sales])/Sum([{MF}/Units])","name":"AUR","format":AURFMT}],
 "rowsBy":[{"id":"bk-cat"}],"values":["bk-sales","bk-gm","bk-gmp","bk-aur"],
 "conditionalFormats":[{"type":"single","columnIds":["bk-sales"],"condition":"IsNotNull","style":{"backgroundColor":"#E7EEF6"}}],
 "name":{"text":"Category mix — sales, margin & AUR","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}

AG_ANALYST={"id":"ag-analyst","name":"Merchandising Analyst",
 "instructions":("You are a merchandising analyst for Big 5 Sporting Goods (a western-US sporting-goods retailer). "
   "Answer questions about net sales, gross margin dollars and rate, units, average unit retail (AUR), and assortment productivity by category, department, brand, price tier and region. "
   "Flag high-productivity categories and thin-margin categories that need markdowns, price-tier rebalancing, or assortment edits. Be concise and quantitative."),
 "dataSources":[{"kind":"table","elementId":"tbl"},{"kind":"table","elementId":"catagg"},{"kind":"table","elementId":"book2"}]}
SCEN_TOOL={"toolId":"create-scenario","kind":"action","name":"Create scenario","description":"Insert a new named assortment/margin scenario row so the user can model it.",
 "steps":[{"kind":"effect","effect":"insert-rows","table":"scenarios","values":{"sc-name":{"type":"agent-input"},"sc-status":{"type":"constant","value":{"type":"text","value":"Draft"}}}}]}
def ag_scenario(with_tool):
    a={"id":"ag-scenario","name":"Planning Copilot","instructions":("You are an assortment & margin planning copilot for Big 5 Sporting Goods. Help model category sales growth, gross-margin-rate changes and markdown depth, and CREATE named scenarios on request using the create-scenario tool."),
       "dataSources":[{"kind":"table","elementId":"book2"}]}
    if with_tool: a["tools"]=[SCEN_TOOL]
    return a
def rail(n,with_agent,rows,agent_id):
    c={"id":f"c-chat{n}","kind":"container","style":dict(CARD)}
    ric={"id":f"chat-ic{n}","kind":"image","source":{"kind":"url","url":"data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="'+RED+'" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>')},"style":{"fit":"contain"}}
    hdr={"id":f"chat-hdr{n}","kind":"text","body":"**Ask Big 5 AI**","verticalAlign":"middle","style":{"color":INK}}
    if with_agent: inner={"id":f"chat{n}","kind":"chat","agentId":agent_id}
    else: inner={"id":f"chat{n}","kind":"text","verticalAlign":"middle","style":{"color":"#22364C","backgroundColor":"#EAF1F8"},"body":"**Ask AI for Insights**\n\n- Which category is most productive (sales x margin)?\n- Where is margin thinnest and why?\n- What sales + markdown mix hits a margin target?"}
    lay=(f'  <GridContainer elementId="c-chat{n}" type="grid" gridColumn="18 / 25" gridRow="{rows}" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="auto">\n'
         f'    <LayoutElement elementId="chat-ic{n}" gridColumn="1 / 3" gridRow="1 / 2"/>\n'
         f'    <LayoutElement elementId="chat-hdr{n}" gridColumn="3 / 13" gridRow="1 / 2"/>\n'
         f'    <LayoutElement elementId="chat{n}" gridColumn="1 / 13" gridRow="2 / 26"/>\n  </GridContainer>')
    return [c,ric,hdr,inner],lay
h1e,h1l=header("1","Merchandising Command Center","Net sales, margin, units & assortment productivity across categories")
def page1(with_agent):
    re,rl=rail(1,with_agent,"20 / 41","ag-analyst")
    elems=[tbl,catagg]+h1e+kpis+[ai_box,ai_ic,ai_hd,ai_sum,filt_c,grain,colorby,ctrl_cat,sbar,matrix_c,matrix_hd,matrix_el,heat,book]+re
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pg">
{h1l}
{chr(10).join(kpilay)}
  <GridContainer elementId="c-ai" type="grid" gridColumn="1 / 25" gridRow="13 / 17" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(4,1fr)"><LayoutElement elementId="ai-ic" gridColumn="1 / 2" gridRow="1 / 2"/><LayoutElement elementId="ai-hd" gridColumn="2 / 25" gridRow="1 / 2"/><LayoutElement elementId="txt-ai" gridColumn="2 / 25" gridRow="2 / 5"/></GridContainer>
  <GridContainer elementId="c-filters" type="grid" gridColumn="1 / 25" gridRow="17 / 20" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <LayoutElement elementId="ctrl-grain" gridColumn="1 / 9" gridRow="1 / 4"/><LayoutElement elementId="ctrl-colorby" gridColumn="9 / 17" gridRow="1 / 4"/><LayoutElement elementId="ctrl-catf" gridColumn="17 / 25" gridRow="1 / 4"/>
  </GridContainer>
  <LayoutElement elementId="sbar" gridColumn="1 / 18" gridRow="20 / 40"/>
  <GridContainer elementId="c-matrix" type="grid" gridColumn="1 / 25" gridRow="42 / 74" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto"><LayoutElement elementId="matrix-hd" gridColumn="1 / 25" gridRow="1 / 2"/><LayoutElement elementId="matrixviz" gridColumn="1 / 25" gridRow="2 / 32"/></GridContainer>
  <LayoutElement elementId="heat" gridColumn="1 / 13" gridRow="76 / 92"/>
  <LayoutElement elementId="book" gridColumn="13 / 25" gridRow="76 / 92"/>
{rl}
</Page>"""
    return elems,lay

# ============ PAGE 2 — ASSORTMENT & MARGIN PLANNER ============
# Fallback planning base (used only when BASE_ROWS_JSON absent). Sales ~ trailing-12mo actuals; margins = CATMARGINS.
DEFAULT_ROWS=[('Athletic Footwear',244000000,0.34),('Team Sports',166000000,0.40),('Apparel',149000000,0.47),
 ('Camping & Outdoors',111000000,0.38),('Fitness & Exercise',111000000,0.30),('Hunting & Fishing',98000000,0.27),
 ('Cycling & Skate',74000000,0.33),('Winter Sports',41000000,0.44),('Game Room & Rec',35000000,0.49),('Water Sports',34000000,0.36)]
if BASE_ROWS_JSON and os.path.exists(BASE_ROWS_JSON):
    _r=json.load(open(BASE_ROWS_JSON))
    ROWS=[(x["category"],int(round(x["sales"])),round(float(x["margin"]),4)) for x in _r]
else:
    ROWS=DEFAULT_ROWS
VALS=",".join(f"('{p}',{rev},{m})" for p,rev,m in ROWS)
SBASE=f"SELECT column1 AS CATEGORY, column2 AS BASE_SALES, column3 AS BASE_MARGIN FROM (VALUES {VALS})"
sbase={"id":"sbase","kind":"table","name":"Category Base","visibleAsSource":True,
 "source":{"connectionId":CONN,"kind":"sql","statement":SBASE},
 "columns":[{"id":"sb-cat2","formula":"[Custom SQL/CATEGORY]","name":"Category"},
            {"id":"sb-rev2","formula":"[Custom SQL/BASE_SALES]","name":"Net Sales","format":CUR},{"id":"sb-mar","formula":"[Custom SQL/BASE_MARGIN]","name":"Margin","format":PCT1}],
 "order":["sb-cat2","sb-rev2","sb-mar"]}
scenarios={"id":"scenarios","kind":"input-table","source":{"kind":"empty","connectionId":CONN},"inputMode":"edit","name":"Scenarios",
 "columns":[{"id":"sc-name","type":"text","name":"Scenario Name"},{"id":"sc-status","type":"text","name":"Status","values":["Draft","Submitted","Approved"],"pills":"color-by-option"}]}
spivot={"id":"spivot","kind":"pivot-table","name":"Scenario Pivot","visibleAsSource":True,
 "source":{"kind":"join","joins":[{"left":{"elementId":"sbase","kind":"table"},"right":{"elementId":"scenarios","kind":"table"},"columns":[{"left":"1","right":"1"}],"joinType":"left-outer"}],"primarySource":{"elementId":"sbase","kind":"table"}},
 "columns":[{"id":"pv-cat","formula":"[Category Base/Category]","name":"Category"},
            {"id":"pv-scen","formula":'Coalesce([Scenarios/Scenario Name],"Base Case")',"name":"Scenario"},
            {"id":"pv-rev","formula":"Sum([Category Base/Net Sales])","name":"Net Sales","format":CUR},
            {"id":"pv-mar","formula":"Avg([Category Base/Margin])","name":"Margin","format":PCT1}],
 "rowsBy":[{"id":"pv-cat"}],"values":["pv-rev","pv-mar"]}
assum={"id":"assum","kind":"input-table","source":{"kind":"linked","from":"spivot"},"inputMode":"edit","name":"Assumptions",
 "columns":[{"id":"ia-cat","key":"pv-cat"},{"id":"ia-scen","key":"pv-scen"},{"id":"ia-rev","key":"pv-rev"},{"id":"ia-mar","key":"pv-mar"},
            {"id":"ia-grow","type":"number","name":"Sales Growth %"},
            {"id":"ia-rate","type":"number","name":"Margin Rate Change (pts)"},
            {"id":"ia-md","type":"number","name":"Markdown %"},
            {"id":"ia-prev","formula":"[Net Sales]*(1+Coalesce([Sales Growth %],0)/100)","name":"Projected Sales","format":CUR},
            {"id":"ia-pm","formula":"[Margin]+Coalesce([Margin Rate Change (pts)],0)/100-Coalesce([Markdown %],0)/100","name":"Projected Margin %","format":PCT1},
            {"id":"ia-pc","formula":"[Projected Sales]*[Projected Margin %]","name":"Projected Margin $","format":CUR}],
 "order":["ia-scen","ia-cat","ia-rev","ia-mar","ia-grow","ia-rate","ia-md","ia-prev","ia-pm","ia-pc"]}
book2={"id":"book2","kind":"table","name":"Book","visibleAsSource":True,
 "source":{"elementId":"assum","kind":"table"},
 "columns":[{"id":"bb-scen","formula":"[Assumptions/Scenario]","name":"Scenario"},
            {"id":"bb-cat","formula":"[Assumptions/Category]","name":"Category"},
            {"id":"bb-brev","formula":"[Assumptions/Net Sales]","name":"Base Sales","format":CUR},
            {"id":"bb-bc","formula":"[Assumptions/Net Sales]*[Assumptions/Margin]","name":"Base Margin $","format":CUR},
            {"id":"bb-prev","formula":"[Assumptions/Projected Sales]","name":"Projected Sales","format":CUR},
            {"id":"bb-pc","formula":"[Assumptions/Projected Margin $]","name":"Projected Margin $","format":CUR}],
 "order":["bb-scen","bb-cat","bb-brev","bb-bc","bb-prev","bb-pc"]}
subs={"id":"subs","kind":"input-table","source":{"kind":"empty","connectionId":CONN},"inputMode":"edit","name":"Submissions",
 "columns":[{"id":"su-scen","type":"text","name":"Scenario"},{"id":"su-status","type":"text","name":"Status","values":["Submitted","Approved"],"pills":"color-by-option"}]}
selctrl={"kind":"control","controlId":"scenarioSelect","id":"ctrl-sel","name":"Active scenario","controlType":"list","selectionMode":"single","mode":"include","value":"Base Case",
 "filters":[{"source":{"kind":"table","elementId":"book2"},"columnId":"bb-scen"}],
 "source":{"kind":"source","source":{"kind":"table","elementId":"book2"},"columnId":"bb-scen"}}
createbtn_tb={"id":"createbtn_tb","kind":"button","text":"Create scenario","appearance":"filled","actions":[{"id":"o1","trigger":"on-click","effects":[{"effect":"open-overlay","overlayId":"createModal"}]}]}
submitbtn={"id":"submitbtn","kind":"button","text":"Submit","appearance":"outline","actions":[{"id":"s1","trigger":"on-click","effects":[{"effect":"insert-rows","table":"subs","values":{"su-scen":{"type":"control","control":"scenarioSelect"},"su-status":{"type":"constant","value":{"type":"text","value":"Submitted"}}}}]}]}
approvebtn={"id":"approvebtn","kind":"button","text":"Approve","appearance":"outline","actions":[{"id":"a1","trigger":"on-click","effects":[{"effect":"insert-rows","table":"subs","values":{"su-scen":{"type":"control","control":"scenarioSelect"},"su-status":{"type":"constant","value":{"type":"text","value":"Approved"}}}}]}]}
namectrl={"kind":"control","controlId":"newScenarioName","id":"ctrl-name","name":"Scenario name","controlType":"text","mode":"equals","case":"insensitive","includeNulls":"when-no-value-is-selected","showOperators":False}
createbtn={"id":"createbtn","kind":"button","text":"Create scenario","appearance":"filled","actions":[{"id":"c1","trigger":"on-click","effects":[
    {"effect":"insert-rows","table":"scenarios","values":{"sc-name":{"type":"control","control":"newScenarioName"},"sc-status":{"type":"constant","value":{"type":"text","value":"Draft"}}}},
    {"effect":"set-control-value","control":"scenarioSelect","value":{"type":"control","control":"newScenarioName"}},
    {"effect":"clear-control","scope":{"type":"control","control":"newScenarioName"}},
    {"effect":"close-overlay"}]}]}
cancelbtn={"id":"cancelbtn","kind":"button","text":"Cancel","appearance":"outline","actions":[{"id":"x1","trigger":"on-click","effects":[{"effect":"close-overlay"}]}]}
mtitle={"id":"mtitle","kind":"text","body":"### New scenario\nName it, then Create. It clones the current book for every category — edit the drivers in the grid.","verticalAlign":"middle","style":{"color":INK}}
modal={"id":"createModal","name":"Create Scenario","type":"modal","modal":{"width":"small","header":{"title":"New scenario","showCloseIcon":"hidden"},"footer":{"primaryCta":{"visible":"hidden"},"secondaryCta":{"visible":"hidden"}}},"elements":[mtitle,namectrl,createbtn,cancelbtn]}
BREV='Sum([Book/Base Sales])'; BC='Sum([Book/Base Margin $])'; PREV='Sum([Book/Projected Sales])'; PC='Sum([Book/Projected Margin $])'
P2K=[("p1","PROJECTED NET SALES",PREV,CUR,BREV),
     ("p2","PROJECTED MARGIN $",PC,CUR,BC),
     ("p3","BLENDED MARGIN %",f"{PC}/{PREV}",PCT1,f"{BC}/{BREV}"),
     ("p4","SALES UPLIFT",f"{PREV}/{BREV}-1",PCT2,None)]
C2=[]; C2L=[]
for i,(elid,title,valf,fmt,compf) in enumerate(P2K):
    e,l=card(elid,"book2",title,valf,compf,"Baseline",fmt,KG[i],trend=None,rowband="8 / 16")
    C2+=e; C2L.append(l.replace("{col}",f"{1+i*6} / {1+(i+1)*6}"))
cbar={"id":"cbar","kind":"bar-chart","source":{"elementId":"book2","kind":"table"},
 "columns":[{"id":"cb-cat","formula":"[Book/Category]","name":"Category"},{"id":"cb-cat2","formula":'"Projected sales"',"name":"Series"},
            {"id":"cb-prev","formula":"Sum([Book/Projected Sales])","name":"Projected Sales","format":CUR}],
 "xAxis":{"columnId":"cb-cat","sort":{"by":"cb-prev","direction":"descending"}},"yAxis":{"columnIds":["cb-prev"]},
 "color":{"by":"category","column":"cb-cat2","scheme":["#E4002B"]},
 "legend":{"visibility":"hidden"},"name":{"text":"Projected net sales by category — active scenario","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}
instr_c={"id":"c-instr","kind":"container","style":dict(TINT)}
instr_ic={"id":"instr-ic","kind":"image","source":{"kind":"url","url":"data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="'+RED+'" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>')},"style":{"fit":"contain"}}
instr_hd={"id":"instr-hd","kind":"text","body":"**How the assortment planner works**","verticalAlign":"middle","style":{"color":INK}}
instr={"id":"instr","kind":"text","body":("**1** — **Create** a named scenario (clones the current book); pick it with **Active scenario**.  **2** — In the grid, type **Sales Growth %**, **Margin Rate Change (pts)**, **Markdown %** per category.  **3** — Cards, chart & Copilot re-project instantly. **Submit → Approve** to lock a plan. Leave a cell blank to hold a driver flat."),
 "verticalAlign":"middle","style":{"color":"#22364C"}}
tb_c={"id":"c-tb","kind":"container","style":dict(CARD)}
h2e,h2l=header("2","Assortment & Margin Planner","Model category sales growth, margin rate & markdown depth")
def page2(with_agent):
    re,rl=rail(2,with_agent,"21 / 56","ag-scenario")
    elems=[tb_c,sbase,scenarios,spivot,book2,subs]+h2e+[selctrl,createbtn_tb,submitbtn,approvebtn]+C2+[instr_c,instr_ic,instr_hd,instr,cbar,assum]+re
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="model">
{h2l}
  <GridContainer elementId="c-tb" type="grid" gridColumn="1 / 25" gridRow="5 / 8" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <LayoutElement elementId="ctrl-sel" gridColumn="1 / 10" gridRow="1 / 4"/>
    <LayoutElement elementId="createbtn_tb" gridColumn="10 / 17" gridRow="1 / 4"/>
    <LayoutElement elementId="submitbtn" gridColumn="17 / 21" gridRow="1 / 4"/>
    <LayoutElement elementId="approvebtn" gridColumn="21 / 25" gridRow="1 / 4"/>
  </GridContainer>
{chr(10).join(C2L)}
  <GridContainer elementId="c-instr" type="grid" gridColumn="1 / 25" gridRow="17 / 21" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(4,1fr)"><LayoutElement elementId="instr-ic" gridColumn="1 / 2" gridRow="1 / 2"/><LayoutElement elementId="instr-hd" gridColumn="2 / 25" gridRow="1 / 2"/><LayoutElement elementId="instr" gridColumn="2 / 25" gridRow="2 / 5"/></GridContainer>
  <LayoutElement elementId="assum" gridColumn="1 / 18" gridRow="21 / 40"/>
  <LayoutElement elementId="cbar" gridColumn="1 / 18" gridRow="40 / 56"/>
{rl}
</Page>"""
    return elems,lay
modal_lay='<Page type="grid" gridTemplateColumns="repeat(24,1fr)" gridTemplateRows="auto" id="createModal"><LayoutElement elementId="mtitle" gridColumn="1 / 25" gridRow="1 / 3"/><LayoutElement elementId="ctrl-name" gridColumn="1 / 25" gridRow="3 / 5"/><LayoutElement elementId="cancelbtn" gridColumn="13 / 19" gridRow="5 / 7"/><LayoutElement elementId="createbtn" gridColumn="19 / 25" gridRow="5 / 7"/></Page>'
theme={"colors":{"text":INK,"highlight":RED,"success":"#15803D","warning":"#F0872E","danger":"#E4002B","darkMode":"hidden"},
 "colorOverrides":{"backgroundCanvas":"#FFFFFF","canvasBackground":"#F4F6F8"},
 "categoricalScheme":["#FFFFFF","#E4002B","#0A2240","#1B4A7A","#3B7DB8","#F0872E","#8A0F1E","#15803D"],
 "fonts":{"textFont":"Inter","dataFont":"Inter"},"pageWidth":"full","tableStyles":{"preset":"presentation","cellSpacing":"small"}}
def build(mode):
    wa=mode!="none"
    p1e,p1l=page1(wa); p2e,p2l=page2(wa)
    s={"name":"Big 5 Sporting Goods — Merchandising Command Center","folderId":FOLDER,"schemaVersion":1,
     "pages":[{"id":"pg","name":"Command Center","elements":p1e},{"id":"model","name":"Assortment Planner","elements":p2e},modal],
     "layout":'<?xml version="1.0" encoding="utf-8"?>\n'+p1l+p2l+modal_lay,"themeOverrides":theme}
    if wa: s["agents"]=[AG_ANALYST, ag_scenario(mode=="tool")]
    return s
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
    if not wid:
        try: wid=[json.loads(resp).get("workbookId")]
        except Exception: wid=[None]
    url=json.loads(urllib.request.urlopen(urllib.request.Request(BASE+f"/v2/workbooks/{wid[0]}",headers=H),timeout=30).read().decode()).get("url") if wid and wid[0] else None
    return ("success: true" in resp or (wid and wid[0])), url, resp, (wid[0] if wid else None)
done=False
for mode in ["tool","basic","none"]:
    spec=build(mode)
    if qa(spec): print("ABORT malformed SVG"); sys.exit(1)
    try:
        ok,url,resp,wid=post(spec); print(f"POST (agent mode={mode}):","ACCEPTED" if ok else resp[:300])
        if ok: print("URL:",url); print("WORKBOOK_ID:",wid); done=True; break
    except urllib.error.HTTPError as e:
        raw=e.read().decode()
        try: msg=json.loads(raw).get("message","")
        except Exception: msg=raw
        print(f"  mode={mode} failed: {e.code} {msg[:260]}")
if not done: print("ALL MODES FAILED")
