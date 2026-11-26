import json
import re
import unicodedata
from datetime import date
from decimal import Decimal


def normal(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def money(text):
    match = re.fullmatch(r"(€|£|\$)\s*(\d+(?:\.\d+)?)\s*(bn|m|k|Th\.)?", str(text), re.I)
    if not match:
        raise ValueError(f"Unsupported market estimate {text!r}")
    symbol, number, suffix = match.groups()
    scale = {"":1,"k":1000,"th.":1000,"m":1000000,"bn":1000000000}[(suffix or "").lower()]
    value = Decimal(number) * scale
    if value != value.to_integral_value():
        raise ValueError("Fractional currency unit")
    return {"€":"EUR","£":"GBP","$":"USD"}[symbol], int(value)


def import_market(db, snapshot, season, data, acquired, candidates, mapping):
    reviewed = json.loads(mapping) if mapping else {}
    acquisition = date.fromisoformat(acquired) if acquired else None
    for line, raw in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        item = json.loads(raw)
        external = re.search(r"/spieler/(\d+)(?:/|$)", item["href"])
        if item.get("type") != "player" or not external:
            raise ValueError(f"Invalid player profile on line {line}")
        external = external[1]
        matches = []
        for identity,name,born,club,comp in candidates:
            if normal(name) in {normal(str(item.get(k) or "")) for k in ("name","name_in_home_country")} and born and born in str(item.get("date_of_birth")):
                matches.append((identity,club,comp))
        # A source club slug is insufficient proof of membership in this season.
        decision, player = "review", None
        evidence = {"candidates": sorted(set(x[0] for x in matches)), "href":item["href"], "rule":"review-v1"}
        if external in reviewed:
            entry = reviewed[external]
            if not entry["reviewer"] or not entry["evidence"] or entry["player_id"] not in {x[0] for x in candidates}:
                raise ValueError("Invalid reviewed mapping")
            date.fromisoformat(entry["reviewed_on"])
            decision, player = "approved", entry["player_id"]
            evidence["approval"] = entry
        db.insert("market_profile", [(snapshot,external,player,decision,json.dumps(evidence),line)])
        observations = {}
        for point in item.get("market_value_history") or []:
            # Accept explicitly dated and denominated offline observations only.
            if not acquisition:
                raise ValueError("Market observations require acquisition date")
            when = date.fromisoformat(point["date"])
            currency,amount = money(point["value"])
            observations[when,currency] = (amount,point["value"])
        current = item.get("current_market_value")
        if current and current.strip() not in {"-","–"}:
            if not acquisition:
                raise ValueError("Current estimate requires a dated export")
            currency,amount = money(current.strip())
            observations[acquisition,currency] = (amount,current)
        for (when,currency),(amount,text) in observations.items():
            if when > acquisition:
                raise ValueError("Estimate after acquisition date")
            db.insert("valuation", [(snapshot,external,when.isoformat(),currency,amount,text,acquisition.isoformat())])
