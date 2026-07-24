"""
Pacific Life — In-Force Command Center. Branded Sigma workbook generator.
Cloned from build_company_command_center.py (canonical current standard); swapped:
brand palette (Pacific Life navy/blue/teal), real white logo, life-insurance reshape SQL,
4 KPIs (In-Force Premium / AUM / Policies In Force / Persistency), AI prompt, the
bespoke Policy Persistency Curve plugin + its synthetic source, and the scenario modeler.

Run: PLUGIN_ID=<id> LOGO_SVG=pl_logo_white.svg python3 build_pacific_life.py <BASE> <TOKEN> <CONN> <FOLDER>
"""
import json,sys,os,base64,urllib.request,urllib.error,xml.dom.minidom as _MD
BASE,TOKEN,CONN,FOLDER=sys.argv[1:5]
AICONN="SNOWFLAKE.CORTEX.COMPLETE"; PERSIST=os.environ.get("PLUGIN_ID","REPLACE_WITH_YOUR_PLUGIN_ID")
H={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"}
def b64(s): return base64.b64encode(s.encode()).decode()
CUR={"kind":"number","formatString":"$.3~s","currencySymbol":"$","decimalSymbol":".","digitGroupingSymbol":",","digitGroupingSize":[3]}
NUM={"kind":"number","formatString":",.3~s"}; PCT2={"kind":"number","formatString":"+,.1%"}; PCT1={"kind":"number","formatString":".1%"}
# ---- Pacific Life brand ----
INK="#0A1F33"; SLATE="#5A6B7B"; NAVY="#003057"; BLUE="#0077C8"; TEAL="#00A9CE"; W="#FFFFFF"
CARD={"backgroundColor":"#FFFFFF","borderColor":"#E3EAF0","borderWidth":1,"borderRadius":"round"}
TINT={"backgroundColor":"#E7F4FA","borderColor":"#C9E6F3","borderWidth":1,"borderRadius":"round"}
def grad(a,b):
    return "data:image/svg+xml;base64,"+b64(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs><rect width="400" height="240" fill="url(#g)"/></svg>')
KG=[grad("#003057","#0077C8"),grad("#0077C8","#00A9CE"),grad("#00506B","#00A9CE"),grad("#0A2A44","#1E6FA8")]
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def timg(text,size=34,color="#FFFFFF",weight=800,anchor="start"):
    t=esc(text); W_=int(len(text)*size*0.60)+24; Hh=int(size*1.7)
    x=3 if anchor=="start" else (W_//2 if anchor=="middle" else W_-3)
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W_} {Hh}" preserveAspectRatio="xMinYMid meet">'
     f'<text x="{x}" y="{int(Hh*0.70)}" text-anchor="{anchor}" font-family="Inter,Arial,sans-serif" font-weight="{weight}" font-size="{size}" fill="{color}">{t}</text></svg>')
    return "data:image/svg+xml;base64,"+b64(svg)
# REAL official Pacific Life wordmark+whale, fetched & recolored white
logo_uri="data:image/svg+xml;base64,"+b64(open(os.environ.get("LOGO_SVG","pl_logo_white.svg")).read())
HDRBG=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 210" preserveAspectRatio="xMidYMid slice">'
  '<defs>'
  '<linearGradient id="hg" x1="0" y1="0" x2="1" y2="0.35"><stop offset="0" stop-color="#00243F"/><stop offset="0.5" stop-color="#0077C8"/><stop offset="1" stop-color="#00A9CE"/></linearGradient>'
  '<radialGradient id="glow" cx="0.84" cy="0.16" r="0.55"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.16"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>'
  '</defs>'
  '<rect width="1600" height="210" fill="url(#hg)"/><rect width="1600" height="210" fill="url(#glow)"/>'
  '<g fill="none" stroke="#CDEBF7" stroke-opacity="0.22" stroke-width="1.4" transform="translate(1380,90)"><circle r="42"/><circle r="78"/><circle r="114"/><line x1="-140" y1="0" x2="140" y2="0"/><line x1="0" y1="-140" x2="0" y2="140"/></g>'
  '</svg>')
HDRBG_URI="data:image/svg+xml;base64,"+b64(HDRBG)
def header(sfx,title,subtitle):
    c={"id":f"c-hdr{sfx}","kind":"container","style":{"borderRadius":"round"},"backgroundImage":{"url":HDRBG_URI,"style":{"fit":"cover"}}}
    lg={"id":f"logo{sfx}","kind":"image","url":logo_uri,"style":{"fit":"scale-down"}}
    tt={"id":f"ttl{sfx}","kind":"image","url":timg(title,34,"#FFFFFF",800,"middle"),"style":{"fit":"scale-down"}}
    sb={"id":f"sub{sfx}","kind":"image","url":timg(subtitle,17,"#DCF1FA",500,"middle"),"style":{"fit":"scale-down"}}
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
    cont={"id":cid,"kind":"container","style":{"borderRadius":"round"},"backgroundImage":{"url":g,"style":{"fit":"cover"}}}
    els=[cont]; inner=""
    if v2f:
        left={"id":f"k-{elid}c","kind":"kpi-chart","source":{"elementId":src,"kind":"table"},
          "columns":[{"id":f"k-{elid}cv","formula":v1f,"name":title,"format":fmt},
                     {"id":f"k-{elid}cc","formula":v2f,"name":"vs "+v2lab,"format":fmt}],
          "value":{"columnId":f"k-{elid}cv","color":W,"fontSize":32},
          "comparisonColumn":{"columnId":f"k-{elid}cc"},
          "comparison":{"display":"delta","colorGood":"#BFEAD6","colorBad":"#FFCFC7","fontSize":13},
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

# ============ PAGE 1 DATA (life-insurance & annuities reshape) ============
MF="Pacific Life"
PRODS=['Term Life','Whole Life','Universal Life','Variable Annuity','Fixed Annuity','Indexed Annuity']
CHAN=['Independent','Wirehouse','Bank & RIA','Direct','Institutional']
REG=['Northeast','Southeast','Midwest','Southwest','West','Pacific']
PREM=[1.2,6.0,4.0,25.0,30.0,28.0]      # annual/single-premium scale per product
FACE=[300.0,120.0,150.0,0.0,0.0,0.0]   # face amount multiple (life products only)
AV=[0.0,0.0,0.0,40.0,45.0,42.0]        # account value factor (annuities only)
def arr(xs): return "ARRAY_CONSTRUCT("+",".join("'"+str(x).replace("'","''")+"'" for x in xs)+")"
def narr(xs): return "ARRAY_CONSTRUCT("+",".join(str(x) for x in xs)+")"
PRODARR=arr(PRODS); CHANARR=arr(CHAN); REGARR=arr(REG); PREMARR=narr(PREM); FACEARR=narr(FACE); AVARR=narr(AV)
SQL=f"""WITH b0 AS (
  SELECT *, MOD(ABS(HASH(PRODUCT_FAMILY)),6) AS PIDX, MOD(ABS(HASH(PRODUCT_LINE)),5) AS CIDX,
    MOD(ABS(HASH(STORE_STATE)),6) AS RIDX, MOD(ABS(HASH(ORDER_NUMBER)),100) AS SIDX,
    DATE_TRUNC('month',DATE) AS USE_MONTH FROM SE_DEMO_DB.BIG_BUYS.BIG_BUYS_POS
  WHERE PRODUCT_FAMILY IS NOT NULL AND PRODUCT_LINE IS NOT NULL AND STORE_STATE IS NOT NULL AND ORDER_NUMBER IS NOT NULL
), base AS (
  SELECT ORDER_NUMBER, DATE, USE_MONTH,
    GET({PRODARR}, PIDX)::string AS PRODUCT_LINE,
    GET({CHANARR}, CIDX)::string AS CHANNEL,
    GET({REGARR}, RIDX)::string AS REGION,
    CASE WHEN SIDX < 84 THEN 'In Force' WHEN SIDX < 94 THEN 'Lapsed' ELSE 'Surrendered' END AS STATUS,
    ORDER_NUMBER AS POLICY,
    MOD(ABS(HASH(CUSTOMER_NAME)),5000000) AS POLICYHOLDER,
    QUANTITY*PRICE*GET({PREMARR}, PIDX) AS ANNUAL_PREMIUM,
    QUANTITY*PRICE*GET({FACEARR}, PIDX) AS FACE_AMOUNT,
    QUANTITY*PRICE*GET({AVARR}, PIDX) AS ACCOUNT_VALUE
  FROM b0
), m AS (SELECT MAX(USE_MONTH) MAXM FROM base)
SELECT base.*, CASE WHEN USE_MONTH>DATEADD('month',-12,(SELECT MAXM FROM m)) THEN 'Current Period'
  WHEN USE_MONTH>DATEADD('month',-24,(SELECT MAXM FROM m)) THEN 'Prior Year' ELSE NULL END AS PERIOD_NAME
FROM base"""
COLS=[("c-date","DATE","Date"),("c-month","USE_MONTH","Month"),("c-period","PERIOD_NAME","Period Name"),
 ("c-prod","PRODUCT_LINE","Product Line"),("c-chan","CHANNEL","Channel"),("c-reg","REGION","Region"),
 ("c-status","STATUS","Status"),("c-policy","POLICY","Policy"),("c-holder","POLICYHOLDER","Policyholder"),
 ("c-prem","ANNUAL_PREMIUM","Annual Premium"),("c-face","FACE_AMOUNT","Face Amount"),("c-av","ACCOUNT_VALUE","Account Value")]
tbl={"id":"tbl","kind":"table","source":{"connectionId":CONN,"statement":SQL,"kind":"sql"},
 "columns":[{"id":c,"formula":f"[Custom SQL/{s}]","name":d} for c,s,d in COLS],"name":MF,"order":[c[0] for c in COLS],"visibleAsSource":True}
# persistency source: synthetic cohort survival by product line x policy year
LAPSE=[('Term Life',0.11),('Whole Life',0.035),('Universal Life',0.07),('Variable Annuity',0.06),('Fixed Annuity',0.05),('Indexed Annuity',0.045)]
LVALS=",".join(f"('{p}',{l})" for p,l in LAPSE)
PERSQL=f"""WITH prods AS (SELECT column1 AS PRODUCT, column2 AS LAPSE FROM (VALUES {LVALS})),
 yrs AS (SELECT SEQ4() AS Y FROM TABLE(GENERATOR(ROWCOUNT=>16)))
SELECT p.PRODUCT AS PRODUCT_LINE, y.Y AS POLICY_YEAR,
  ROUND(POWER(1-p.LAPSE, y.Y)*100, 1) AS IN_FORCE_PCT
FROM prods p CROSS JOIN yrs y"""
persist={"id":"persist","kind":"table","name":"Persistency Curve","visibleAsSource":True,
 "source":{"connectionId":CONN,"kind":"sql","statement":PERSQL},
 "columns":[{"id":"pc-prod","formula":"[Custom SQL/PRODUCT_LINE]","name":"Product Line"},
            {"id":"pc-year","formula":"[Custom SQL/POLICY_YEAR]","name":"Policy Year"},
            {"id":"pc-pct","formula":"[Custom SQL/IN_FORCE_PCT]","name":"% In Force","format":PCT1}],
 "order":["pc-prod","pc-year","pc-pct"]}

_P='[{0}/Period Name]="§"'.format(MF)
_IF='[{0}/Status]="In Force"'.format(MF)
KDEFS=[("prem","IN-FORCE PREMIUM",f'SumIf([{MF}/Annual Premium],{_P},{_IF})',CUR,f'Sum([{MF}/Annual Premium])'),
       ("aum","ASSETS UNDER MGMT",f'SumIf([{MF}/Account Value],{_P})',CUR,f'Sum([{MF}/Account Value])'),
       ("pol","POLICIES IN FORCE",f'CountDistinct(If({_P},If({_IF},[{MF}/Policy],Null),Null))',NUM,f'CountDistinct([{MF}/Policy])'),
       ("pers","PERSISTENCY RATE",f'CountDistinct(If({_P},If({_IF},[{MF}/Policy],Null),Null))/CountDistinct(If({_P},[{MF}/Policy],Null))',PCT1,f'CountDistinct(If({_IF},[{MF}/Policy],Null))/CountDistinct([{MF}/Policy])')]
kpis=[]; kpilay=[]
for i,(elid,t,mf,fmt,tr) in enumerate(KDEFS):
    cur=mf.replace("§","Current Period"); pri=mf.replace("§","Prior Year")
    e,l=card(elid,"tbl",t,cur,pri,"Prior Year",fmt,KG[i],trend=tr,rowband="5 / 13"); kpis+=e; kpilay.append(l.replace("{col}",f"{1+i*6} / {1+(i+1)*6}"))

ai_body=('{{ Replace(CallText("'+AICONN+'", "CLAUDE-4-SONNET", '
 '"You are an in-force block analyst at Pacific Life (products: Term Life, Whole Life, Universal Life, Variable, Fixed & Indexed Annuities). '
 'In two concise sentences summarize the in-force block given In-Force Premium of $" '
 '& Text(Round(SumIf(['+MF+'/Annual Premium],['+MF+'/Status]="In Force")/1000000,0)) & "M, Assets Under Management of $" '
 '& Text(Round(Sum(['+MF+'/Account Value])/1000000000,1)) & "B, and a blended persistency of " '
 '& Text(Round(CountDistinct(If(['+MF+'/Status]="In Force",['+MF+'/Policy],Null))/CountDistinct(['+MF+'/Policy])*100,1)) & "%. Note the leading product line and the persistency pattern by policy year."), \'"\', \'\') }}')
ai_box={"id":"c-ai","kind":"container","style":dict(TINT)}
ai_ic={"id":"ai-ic","kind":"image","url":"data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="'+BLUE+'" stroke="'+BLUE+'" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>'),"style":{"fit":"contain"}}
ai_hd={"id":"ai-hd","kind":"text","body":"**AI insight**","verticalAlign":"middle","style":{"color":INK}}
ai_sum={"id":"txt-ai","kind":"text","body":ai_body,"verticalAlign":"middle","style":{"color":"#12354F"}}
grain={"kind":"control","controlId":"DateGrain","id":"ctrl-grain","name":"Date Grain","controlType":"segmented","value":"Month","source":{"kind":"manual","valueType":"text","values":["Quarter","Month","Week","Day"]}}
colorby={"kind":"control","controlId":"ColorBy","id":"ctrl-colorby","name":"Color By","controlType":"segmented","value":"Product Line","source":{"kind":"manual","valueType":"text","values":["Product Line","Channel","Region"]}}
ctrl_prod={"kind":"control","controlId":"ProdF","id":"ctrl-prodf","name":"Product Line","controlType":"list","selectionMode":"multiple","mode":"include","values":[],"filters":[{"source":{"kind":"table","elementId":"tbl"},"columnId":"c-prod"}],"source":{"kind":"source","source":{"kind":"table","elementId":"tbl"},"columnId":"c-prod"}}
filt_c={"id":"c-filters","kind":"container","style":dict(CARD)}
sbar={"id":"sbar","kind":"bar-chart","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"sbm","formula":f'Switch([DateGrain],"Quarter",DateTrunc("quarter",[{MF}/Date]),"Week",DateTrunc("week",[{MF}/Date]),"Day",DateTrunc("day",[{MF}/Date]),DateTrunc("month",[{MF}/Date]))',"name":"Period","format":{"kind":"datetime","formatString":"%b %d, %Y"}},
            {"id":"sbv","formula":f"Sum([{MF}/Annual Premium])","name":"Annual Premium","format":CUR},
            {"id":"sbc","formula":f'Switch([ColorBy],"Product Line",[{MF}/Product Line],"Channel",[{MF}/Channel],"Region",[{MF}/Region])',"name":"Series"},
            {"id":"sb-prod","formula":f"[{MF}/Product Line]","name":"Product Line"},{"id":"sb-chan","formula":f"[{MF}/Channel]","name":"Channel"},{"id":"sb-reg","formula":f"[{MF}/Region]","name":"Region"}],
 "xAxis":{"columnId":"sbm"},"yAxis":{"columnIds":["sbv"]},"color":{"by":"category","column":"sbc","scheme":["#0077C8","#00A9CE","#003057","#5BC2E7","#8E44AD","#F0872E","#00857C","#B21E5B"]},"stacking":"stacked",
 "dataLabel":{"labels":"hidden"},"legend":{"visibility":"visible"},"name":{"text":"Annualized premium by period & product line","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}
pcurve_c={"id":"c-pcurve","kind":"container","style":dict(CARD)}
pcurve_hd={"id":"pcurve-hd","kind":"text","body":"**Policy persistency — % in force by policy year**","verticalAlign":"middle","style":{"color":INK}}
pcurve_el={"id":"pcurveviz","kind":"plugin","pluginId":PERSIST,"config":{"source":{"kind":"element","elementId":"persist"},"series":"pc-prod","year":"pc-year","value":"pc-pct"}}
heat={"id":"heat","kind":"pivot-table","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"hm","formula":f"[{MF}/Product Line]","name":"Product Line"},{"id":"hp","formula":f"[{MF}/Region]","name":"Region"},{"id":"hv","formula":f"Sum([{MF}/Annual Premium])","name":"Annual Premium","format":CUR}],
 "rowsBy":[{"id":"hm"}],"columnsBy":[{"id":"hp"}],"values":["hv"],
 "conditionalFormats":[{"type":"single","columnIds":["hv"],"condition":"IsNotNull","style":{"backgroundColor":"#DCEEF9"}}],
 "name":{"text":"Premium — Product x Region","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}
book={"id":"book","kind":"pivot-table","source":{"elementId":"tbl","kind":"table"},
 "columns":[{"id":"bk-prod","formula":f"[{MF}/Product Line]","name":"Product Line"},
            {"id":"bk-prem","formula":f"Sum([{MF}/Annual Premium])","name":"Premium","format":CUR},
            {"id":"bk-av","formula":f"Sum([{MF}/Account Value])","name":"AUM","format":CUR},
            {"id":"bk-pers","formula":f'CountDistinct(If({_IF},[{MF}/Policy],Null))/CountDistinct([{MF}/Policy])',"name":"Persistency","format":PCT1}],
 "rowsBy":[{"id":"bk-prod"}],"values":["bk-prem","bk-av","bk-pers"],
 "conditionalFormats":[{"type":"single","columnIds":["bk-prem"],"condition":"IsNotNull","style":{"backgroundColor":"#DCEEF9"}}],
 "name":{"text":"Product mix","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}

AG_COPILOT={"id":"ag-copilot","name":"Pacific Life Copilot",
 "instructions":("You are an in-force block analyst for Pacific Life (products: Term Life, Whole Life, Universal Life, Variable, Fixed & Indexed Annuities; channels Independent, Wirehouse, Bank & RIA, Direct, Institutional; six regions). "
   "Answer questions about in-force annualized premium, assets under management (annuity account value), policies in force, persistency/lapse by product line and policy year, channel and regional mix, and how new-business growth or lapse changes move the block. Be concise and quantitative."),
 "dataSources":[{"kind":"table","elementId":"tbl"},{"kind":"table","elementId":"book2"}]}
SCEN_TOOL={"toolId":"create-scenario","kind":"action","name":"Create scenario","description":"Insert a new named scenario row into the Scenarios table so the user can model it.",
 "steps":[{"kind":"effect","effect":"insert-rows","table":"scenarios","values":{"sc-name":{"type":"agent-input"},"sc-status":{"type":"constant","value":{"type":"text","value":"Draft"}}}}]}
def ag_scenario(with_tool):
    a={"id":"ag-scenario","name":"Scenario Copilot","instructions":("You are a growth & persistency scenario copilot for Pacific Life. Help model new-business growth, lapse-rate changes, and expense changes by product line, and CREATE named scenarios on request using the create-scenario tool."),
       "dataSources":[{"kind":"table","elementId":"book2"}]}
    if with_tool: a["tools"]=[SCEN_TOOL]
    return a
def rail(n,with_agent,rows,agent_id):
    c={"id":f"c-chat{n}","kind":"container","style":dict(CARD)}
    ric={"id":f"chat-ic{n}","kind":"image","url":"data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="'+BLUE+'" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>'),"style":{"fit":"contain"}}
    hdr={"id":f"chat-hdr{n}","kind":"text","body":"**Ask Pacific Life AI**","verticalAlign":"middle","style":{"color":INK}}
    if with_agent: inner={"id":f"chat{n}","kind":"chat","agentId":agent_id}
    else: inner={"id":f"chat{n}","kind":"text","verticalAlign":"middle","style":{"color":"#12354F","backgroundColor":"#E7F4FA"},"body":"**Ask AI for Insights**\n\n- Which product line holds the most in-force premium?\n- Where does persistency drop fastest by policy year?\n- What new-business + lapse mix hits a premium target?"}
    lay=(f'  <GridContainer elementId="c-chat{n}" type="grid" gridColumn="18 / 25" gridRow="{rows}" gridTemplateColumns="repeat(12, 1fr)" gridTemplateRows="auto">\n'
         f'    <LayoutElement elementId="chat-ic{n}" gridColumn="1 / 3" gridRow="1 / 2"/>\n'
         f'    <LayoutElement elementId="chat-hdr{n}" gridColumn="3 / 13" gridRow="1 / 2"/>\n'
         f'    <LayoutElement elementId="chat{n}" gridColumn="1 / 13" gridRow="2 / 26"/>\n  </GridContainer>')
    return [c,ric,hdr,inner],lay
h1e,h1l=header("1","In-Force Command Center","Premium, AUM, policies & persistency across products")
def page1(with_agent):
    re,rl=rail(1,with_agent,"20 / 41","ag-copilot")
    elems=[tbl,persist]+h1e+kpis+[ai_box,ai_ic,ai_hd,ai_sum,filt_c,grain,colorby,ctrl_prod,sbar,pcurve_c,pcurve_hd,pcurve_el,heat,book]+re
    lay=f"""<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="pg">
{h1l}
{chr(10).join(kpilay)}
  <GridContainer elementId="c-ai" type="grid" gridColumn="1 / 25" gridRow="13 / 17" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="repeat(4,1fr)"><LayoutElement elementId="ai-ic" gridColumn="1 / 2" gridRow="1 / 2"/><LayoutElement elementId="ai-hd" gridColumn="2 / 25" gridRow="1 / 2"/><LayoutElement elementId="txt-ai" gridColumn="2 / 25" gridRow="2 / 5"/></GridContainer>
  <GridContainer elementId="c-filters" type="grid" gridColumn="1 / 25" gridRow="17 / 20" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <LayoutElement elementId="ctrl-grain" gridColumn="1 / 9" gridRow="1 / 4"/><LayoutElement elementId="ctrl-colorby" gridColumn="9 / 17" gridRow="1 / 4"/><LayoutElement elementId="ctrl-prodf" gridColumn="17 / 25" gridRow="1 / 4"/>
  </GridContainer>
  <LayoutElement elementId="sbar" gridColumn="1 / 18" gridRow="20 / 40"/>
  <GridContainer elementId="c-pcurve" type="grid" gridColumn="1 / 25" gridRow="42 / 74" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto"><LayoutElement elementId="pcurve-hd" gridColumn="1 / 25" gridRow="1 / 2"/><LayoutElement elementId="pcurveviz" gridColumn="1 / 25" gridRow="2 / 32"/></GridContainer>
  <LayoutElement elementId="heat" gridColumn="1 / 13" gridRow="76 / 92"/>
  <LayoutElement elementId="book" gridColumn="13 / 25" gridRow="76 / 92"/>
{rl}
</Page>"""
    return elems,lay

# ============ PAGE 2 — GROWTH & PERSISTENCY SCENARIO MODELER ============
ROWS=[('Term Life','Life',900000000,0.18),('Whole Life','Life',2100000000,0.32),
 ('Universal Life','Life',1400000000,0.27),('Variable Annuity','Annuity',3200000000,0.16),
 ('Fixed Annuity','Annuity',2600000000,0.14),('Indexed Annuity','Annuity',1800000000,0.19)]
VALS=",".join(f"('{p}','{c}',{rev},{m})" for p,c,rev,m in ROWS)
SBASE=f"SELECT column1 AS PRODUCT, column2 AS GRP, column3 AS BASE_PREM, column4 AS BASE_SPREAD FROM (VALUES {VALS})"
sbase={"id":"sbase","kind":"table","name":"Product Base","visibleAsSource":True,
 "source":{"connectionId":CONN,"kind":"sql","statement":SBASE},
 "columns":[{"id":"sb-prod2","formula":"[Custom SQL/PRODUCT]","name":"Product Line"},{"id":"sb-grp","formula":"[Custom SQL/GRP]","name":"Segment"},
            {"id":"sb-prem2","formula":"[Custom SQL/BASE_PREM]","name":"In-Force Premium","format":CUR},{"id":"sb-spr","formula":"[Custom SQL/BASE_SPREAD]","name":"Net Spread","format":PCT1}],
 "order":["sb-prod2","sb-grp","sb-prem2","sb-spr"]}
scenarios={"id":"scenarios","kind":"input-table","source":{"kind":"empty","connectionId":CONN},"inputMode":"edit","name":"Scenarios",
 "columns":[{"id":"sc-name","type":"text","name":"Scenario Name"},{"id":"sc-status","type":"text","name":"Status","values":["Draft","Submitted","Approved"],"pills":"color-by-option"}]}
spivot={"id":"spivot","kind":"pivot-table","name":"Scenario Pivot","visibleAsSource":True,
 "source":{"kind":"join","joins":[{"left":{"elementId":"sbase","kind":"table"},"right":{"elementId":"scenarios","kind":"table"},"columns":[{"left":"1","right":"1"}],"joinType":"left-outer"}],"primarySource":{"elementId":"sbase","kind":"table"}},
 "columns":[{"id":"pv-prod","formula":"[Product Base/Product Line]","name":"Product Line"},
            {"id":"pv-grp","formula":"[Product Base/Segment]","name":"Segment"},
            {"id":"pv-scen","formula":'Coalesce([Scenarios/Scenario Name],"Base Case")',"name":"Scenario"},
            {"id":"pv-prem","formula":"Sum([Product Base/In-Force Premium])","name":"In-Force Premium","format":CUR},
            {"id":"pv-spr","formula":"Avg([Product Base/Net Spread])","name":"Net Spread","format":PCT1}],
 "rowsBy":[{"id":"pv-prod"},{"id":"pv-grp"}],"values":["pv-prem","pv-spr"]}
assum={"id":"assum","kind":"input-table","source":{"kind":"linked","from":"spivot"},"inputMode":"edit","name":"Assumptions",
 "columns":[{"id":"ia-prod","key":"pv-prod"},{"id":"ia-grp","key":"pv-grp"},{"id":"ia-scen","key":"pv-scen"},{"id":"ia-prem","key":"pv-prem"},{"id":"ia-spr","key":"pv-spr"},
            {"id":"ia-grow","type":"number","name":"New Business Growth %"},
            {"id":"ia-lapse","type":"number","name":"Lapse Change %"},
            {"id":"ia-exp","type":"number","name":"Expense Change %"},
            {"id":"ia-pprem","formula":"[In-Force Premium]*(1+Coalesce([New Business Growth %],0)/100)","name":"Projected Premium","format":CUR},
            {"id":"ia-pspr","formula":"[Net Spread]*(1-Coalesce([Lapse Change %],0)/100)*(1-Coalesce([Expense Change %],0)/100)","name":"Projected Spread","format":PCT1},
            {"id":"ia-pc","formula":"[Projected Premium]*[Projected Spread]","name":"Projected Contribution","format":CUR}],
 "order":["ia-scen","ia-prod","ia-grp","ia-prem","ia-grow","ia-lapse","ia-exp","ia-pprem","ia-pspr","ia-pc"]}
book2={"id":"book2","kind":"table","name":"Book","visibleAsSource":True,
 "source":{"elementId":"assum","kind":"table"},
 "columns":[{"id":"bb-scen","formula":"[Assumptions/Scenario]","name":"Scenario"},
            {"id":"bb-prod","formula":"[Assumptions/Product Line]","name":"Product Line"},
            {"id":"bb-bprem","formula":"[Assumptions/In-Force Premium]","name":"Base Premium","format":CUR},
            {"id":"bb-bc","formula":"[Assumptions/In-Force Premium]*[Assumptions/Net Spread]","name":"Base Contribution","format":CUR},
            {"id":"bb-pprem","formula":"[Assumptions/Projected Premium]","name":"Projected Premium","format":CUR},
            {"id":"bb-pc","formula":"[Assumptions/Projected Contribution]","name":"Projected Contribution","format":CUR}],
 "order":["bb-scen","bb-prod","bb-bprem","bb-bc","bb-pprem","bb-pc"]}
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
mtitle={"id":"mtitle","kind":"text","body":"### New scenario\nName it, then Create. It clones the current book for every product line — edit the assumptions in the grid.","verticalAlign":"middle","style":{"color":INK}}
modal={"id":"createModal","name":"Create Scenario","type":"modal","modal":{"width":"small","header":{"title":"New scenario","showCloseIcon":"hidden"},"footer":{"primaryCta":{"visible":"hidden"},"secondaryCta":{"visible":"hidden"}}},"elements":[mtitle,namectrl,createbtn,cancelbtn]}
BPREM='Sum([Book/Base Premium])'; BC='Sum([Book/Base Contribution])'; PPREM='Sum([Book/Projected Premium])'; PC='Sum([Book/Projected Contribution])'
P2K=[("p1","PROJECTED PREMIUM",PPREM,CUR,BPREM),
     ("p2","PROJECTED CONTRIBUTION",PC,CUR,BC),
     ("p3","BLENDED SPREAD",f"{PC}/{PPREM}",PCT1,f"{BC}/{BPREM}"),
     ("p4","PREMIUM UPLIFT",f"{PPREM}/{BPREM}-1",PCT2,None)]
C2=[]; C2L=[]
for i,(elid,title,valf,fmt,compf) in enumerate(P2K):
    e,l=card(elid,"book2",title,valf,compf,"Baseline",fmt,KG[i],trend=None,rowband="8 / 16")
    C2+=e; C2L.append(l.replace("{col}",f"{1+i*6} / {1+(i+1)*6}"))
cbar={"id":"cbar","kind":"bar-chart","source":{"elementId":"book2","kind":"table"},
 "columns":[{"id":"cb-prod","formula":"[Book/Product Line]","name":"Product Line"},{"id":"cb-cat2","formula":'"Projected premium"',"name":"Series"},
            {"id":"cb-pprem","formula":"Sum([Book/Projected Premium])","name":"Projected Premium","format":CUR}],
 "xAxis":{"columnId":"cb-prod","sort":{"by":"cb-pprem","direction":"descending"}},"yAxis":{"columnIds":["cb-pprem"]},
 "color":{"by":"category","column":"cb-cat2","scheme":["#0077C8"]},
 "legend":{"visibility":"hidden"},"name":{"text":"Projected in-force premium by product — active scenario","fontWeight":"bold","fontSize":15,"color":INK},"style":dict(CARD)}
instr_c={"id":"c-instr","kind":"container","style":dict(TINT)}
instr_ic={"id":"instr-ic","kind":"image","url":"data:image/svg+xml;base64,"+b64('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="'+BLUE+'" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>'),"style":{"fit":"contain"}}
instr_hd={"id":"instr-hd","kind":"text","body":"**How the scenario modeler works**","verticalAlign":"middle","style":{"color":INK}}
instr={"id":"instr","kind":"text","body":("**1** — **Create** a named scenario (clones the current book); pick it with **Active scenario**.  **2** — In the grid, type **New Business Growth %**, **Lapse Change %**, **Expense Change %** per product.  **3** — Cards, chart & Copilot re-project instantly. **Submit → Approve** to lock a plan. Leave a cell blank to hold a driver flat."),
 "verticalAlign":"middle","style":{"color":"#12354F"}}
tb_c={"id":"c-tb","kind":"container","style":dict(CARD)}
h2e,h2l=header("2","Growth & Persistency Scenario Modeler","Model new-business growth, lapse & expense by product line")
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
theme={"colors":{"text":INK,"highlight":BLUE,"success":"#00857C","warning":"#F0872E","danger":"#B21E5B","darkMode":"hidden"},
 "colorOverrides":{"backgroundCanvas":"#FFFFFF","canvasBackground":"#F1F5F8"},
 "categoricalScheme":["#FFFFFF","#0077C8","#00A9CE","#003057","#5BC2E7","#8E44AD","#00857C","#F0872E"],
 "fonts":{"textFont":"Inter","dataFont":"Inter"},"pageWidth":"full","tableStyles":{"preset":"presentation","cellSpacing":"small"}}
def build(mode):
    wa=mode!="none"
    p1e,p1l=page1(wa); p2e,p2l=page2(wa)
    s={"name":"Pacific Life — In-Force Command Center","folderId":FOLDER,"schemaVersion":1,
     "pages":[{"id":"pg","name":"Command Center","elements":p1e},{"id":"model","name":"Scenario Modeler","elements":p2e},modal],
     "layout":'<?xml version="1.0" encoding="utf-8"?>\n'+p1l+p2l+modal_lay,"themeOverrides":theme}
    if wa: s["agents"]=[AG_COPILOT, ag_scenario(mode=="tool")]
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
    try:
        j=json.loads(resp); wid=[j.get("workbookId")] if j.get("workbookId") else wid
    except Exception: pass
    url=json.loads(urllib.request.urlopen(urllib.request.Request(BASE+f"/v2/workbooks/{wid[0]}",headers=H),timeout=30).read().decode()).get("url") if wid and wid[0] else None
    return ("success: true" in resp or (wid and wid[0])), url, resp
done=False
for mode in ["tool","basic","none"]:
    spec=build(mode)
    if qa(spec): print("ABORT malformed SVG"); sys.exit(1)
    try:
        ok,url,resp=post(spec); print(f"POST (agent mode={mode}):","ACCEPTED" if ok else resp[:300])
        if ok: print("URL:",url); done=True; break
    except urllib.error.HTTPError as e:
        raw=e.read().decode()
        try: msg=json.loads(raw).get("message","")
        except Exception: msg=raw
        print(f"  mode={mode} failed: {e.code} {msg[:220]}")
if not done: print("ALL MODES FAILED")
