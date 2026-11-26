"""Role fit across qualified club stints in a single season."""
import argparse
import json
import math
from bisect import bisect_left, bisect_right
from datetime import date

from .db import database

# label, subject, source column, convert count to per 90, direction
FEATURES = {
    "goals": ("Non-penalty goals / 90","Standard Stats","Per 90 Minutes.G-PK",False,1),
    "assists": ("Assists / 90","Standard Stats","Per 90 Minutes.Ast",False,1),
    "shots": ("Shots on target / 90","Shooting","Standard.SoT/90",False,1),
    "interceptions": ("Interceptions / 90","Miscellaneous Stats","Performance.Int",True,1),
    "tackles": ("Tackles won / 90","Miscellaneous Stats","Performance.TklW",True,1),
    "saves": ("Save percentage","Goalkeeping","Performance.Save%",False,1),
    "conceded": ("Goals conceded / 90","Goalkeeping","Performance.GA90",False,-1),
}
ROLES = {"FW":{"goals":5,"shots":3,"assists":2}, "MF":{"assists":4,"interceptions":3,"tackles":3},
         "DF":{"interceptions":5,"tackles":5}, "GK":{"saves":7,"conceded":3}}


OUTFIELD_STATS = {
    ("Standard Stats","Playing Time.MP"): "Appearances",
    ("Standard Stats","Per 90 Minutes.Gls"): "Goals / 90",
    ("Standard Stats","Per 90 Minutes.Ast"): "Assists / 90",
    ("Shooting","Standard.Sh/90"): "Shots / 90",
    ("Standard Stats","Performance.Gls"): "Goals",
    ("Standard Stats","Performance.Ast"): "Assists",
    ("Shooting","Standard.Sh"): "Shots",
    ("Shooting","Standard.SoT"): "Shots on target",
    ("Miscellaneous Stats","Performance.Int"): "Interceptions",
    ("Miscellaneous Stats","Performance.TklW"): "Tackles won",
    ("Standard Stats","Performance.CrdY"): "Yellow cards",
}
KEEPER_STATS = {
    ("Goalkeeping","Playing Time.MP"): "Appearances",
    ("Goalkeeping","Performance.Saves"): "Saves",
    ("Goalkeeping","Performance.Save%"): "Save %",
    ("Goalkeeping","Performance.CS"): "Clean sheets",
    ("Goalkeeping","Performance.GA"): "Goals conceded",
    ("Goalkeeping","Penalty Kicks.PKsv"): "Penalties saved",
}


RATE_BANDS = ((0,0.1),(0.1,0.25),(0.25,0.5),(0.5,0.75),(0.75,1),(1,math.inf))
RATE_LABELS = {"goals":"Goals / 90","assists":"Assists / 90","shots":"Shots / 90"}


def player_names(season="2025-2026"):
    with database() as db:
        return [row[0] for row in db.run("""SELECT DISTINCT p.name FROM player p
            JOIN stint s ON s.player=p.id JOIN active_snapshot a ON a.snapshot=s.snapshot
            WHERE a.season=? ORDER BY p.name""",(season,))]


def rank(role="FW", season="2025-2026", weights=None, minutes=450, min_age=None, max_age=None,
         budget=None, currency="EUR", as_of=None, search="", league="", offset=0, limit=40, url=None, max_minutes=None, min_budget=None, player_name="", rate_bands=None):
    if role not in ROLES:
        raise ValueError("Choose FW, MF, DF or GK")
    weights = ROLES[role] if weights is None else weights
    allowed = {"saves","conceded"} if role=="GK" else set(FEATURES)-{"saves","conceded"}
    if not isinstance(weights,dict) or not weights or not set(weights)<=allowed or any(
        type(w) not in (int,float) or not math.isfinite(w) or not 0<=w<=100 for w in weights.values()
    ) or sum(weights.values())<=0:
        raise ValueError("Supply positive total role-compatible weights between 0 and 100")
    if minutes<1 or offset<0 or not 1<=limit<=200 or any(a is not None and not 0<=a<=100 for a in (min_age,max_age)):
        raise ValueError("Invalid minutes, age or pagination")
    if min_age is not None and max_age is not None and min_age>max_age:
        raise ValueError("Minimum age exceeds maximum")
    if currency not in ("EUR","GBP","USD") or budget is not None and (not math.isfinite(budget) or budget<0):
        raise ValueError("Invalid budget or currency")
    if max_minutes is not None and max_minutes < minutes:
        raise ValueError("Maximum minutes below minimum")
    if min_budget is not None and (not math.isfinite(min_budget) or min_budget<0 or budget is not None and min_budget>budget):
        raise ValueError("Invalid budget range")
    if rate_bands is None:
        rate_bands = {}
    if (not isinstance(rate_bands,dict) or not set(rate_bands)<=RATE_LABELS.keys()
        or any(type(index) is not int or not 0<=index<len(RATE_BANDS) for index in rate_bands.values())
        or role=="GK" and rate_bands):
        raise ValueError("Choose a valid outfield per-90 range")
    cutoff = date.fromisoformat(as_of) if as_of else date.today()
    with database(url) as db:
        active = db.run("SELECT snapshot FROM active_snapshot WHERE season=?", (season,)).fetchone()
        if not active:
            raise ValueError("Season has no published import")
        snapshot = active[0]
        features = {(FEATURES[k][1],FEATURES[k][2]): k for k,w in weights.items() if w}
        display = KEEPER_STATS if role=="GK" else OUTFIELD_STATS
        requested = features.keys() | display.keys()
        predicates = " OR ".join("(m.subject=? AND m.field=?)" for _ in requested)
        params = [part for pair in requested for part in pair]
        rows = db.run(f"""SELECT s.id,p.id,p.name,c.name,s.competition,s.age,s.minutes,s.position,
                                 m.subject,m.field,m.value,f.source_row
            FROM stint s JOIN player p ON p.id=s.player JOIN club c ON c.id=s.club
            LEFT JOIN measurement m ON m.stint=s.id AND ({predicates})
            LEFT JOIN performance f ON f.stint=m.stint AND f.subject=m.subject
            WHERE s.snapshot=? AND s.minutes>=? AND s.position LIKE ?""",
            (*params,snapshot,minutes,role+"%"))
        pool = {}
        for stint,pid,name,club,comp,age,mins,pos,subject,col,value,line in rows:
            rec = pool.setdefault(stint,dict(stint=stint,player_id=pid,name=name,club=club,competition=comp,
                                             age=age,minutes=mins,position=pos,metrics={},stats=dict.fromkeys(display.values())))
            if value is not None:
                if (subject,col) in display:
                    rec["stats"][display[subject,col]] = value
                if (subject,col) not in features:
                    continue
                key = features[subject,col]
                label,_,_,per90,_ = FEATURES[key]
                rec["metrics"][key] = dict(label=label,value=value*90/mins if per90 else value,
                                           source=subject,column=col,row=line)
        prices = {}
        for pid,amount,when,unit,external in db.run("""SELECT m.player,v.amount,v.effective,v.currency,v.external_id FROM valuation v JOIN market_profile m
            ON m.snapshot=v.snapshot AND m.external_id=v.external_id WHERE v.snapshot=?
            AND v.effective<=? AND v.acquired<=? AND m.player IS NOT NULL ORDER BY v.effective,v.acquired,CASE WHEN v.currency=? THEN 1 ELSE 0 END,v.currency""",
            (snapshot,cutoff.isoformat(),cutoff.isoformat(),currency)):
            prices[pid] = dict(amount=amount,currency=unit,date=when,source="Transfermarkt",external_id=external)
    distributions = {k:sorted(r["metrics"][k]["value"]*FEATURES[k][4] for r in pool.values() if k in r["metrics"]) for k in weights}
    results = []
    for r in pool.values():
        evidence = r["metrics"]
        score = 0
        for key,metric in evidence.items():
            values = distributions[key]
            if len(values)<3:
                continue
            v = metric["value"] * FEATURES[key][4]
            midpoint = (bisect_left(values,v)+bisect_right(values,v)-1)/2
            pct = 100*midpoint/(len(values)-1)
            contribution = pct*weights[key]/sum(weights.values())
            metric.update(percentile=pct,contribution=contribution,peers=len(values))
            score += contribution
        r["coverage"] = sum(weights[k] for k,m in evidence.items() if "percentile" in m)/sum(weights.values())
        r["score"] = round(score,4) if all(w==0 or "percentile" in evidence.get(k,{}) for k,w in weights.items()) else None
        price = r["valuation"] = prices.get(r["player_id"])
        if min_age is not None and (r["age"] is None or r["age"]<min_age): continue
        if max_age is not None and (r["age"] is None or r["age"]>max_age): continue
        if max_minutes is not None and r["minutes"]>max_minutes: continue
        if min_budget is not None or budget is not None:
            if price is None or price["currency"]!=currency: continue
            if min_budget is not None and price["amount"]<min_budget: continue
            if budget is not None and price["amount"]>budget: continue
        if league and league != r["competition"]: continue
        if player_name and r["name"] != player_name: continue
        if search.casefold() not in r["name"].casefold(): continue
        if any(r["stats"][RATE_LABELS[key]] is None or
               not RATE_BANDS[index][0] <= r["stats"][RATE_LABELS[key]] < RATE_BANDS[index][1]
               for key,index in rate_bands.items()):
            continue
        results.append(r)
    results.sort(key=lambda r:(r["score"] is None,-(r["score"] or 0),r["name"],r["stint"]))
    return dict(version="fit-1",snapshot=snapshot,season=season,role=role,weights=weights,as_of=cutoff.isoformat(),
                cohort=len(pool),valued=sum(r["player_id"] in prices for r in pool.values()),
                total=len(results),results=results[offset:offset+limit])


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role",choices=ROLES,default="FW")
    parser.add_argument("--weights",type=json.loads)
    for key in ("minutes","min-age","max-age","budget","limit"):
        parser.add_argument("--"+key,type=int,default=argparse.SUPPRESS)
    for key in ("season","currency","as-of","league","search"):
        parser.add_argument("--"+key,default=argparse.SUPPRESS)
    print(json.dumps(rank(**vars(parser.parse_args())),indent=2))
