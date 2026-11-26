"""Validate the complete batch before atomically publishing a season snapshot."""
import argparse
import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from pathlib import Path

from .db import database
from .market import import_market

VERSION = "fbref-2.market-1"
SUBJECTS = ("Clubs", "Playing Time", "Standard Stats", "Shooting", "Miscellaneous Stats", "Goalkeeping")
LEAGUES = {"eng ENG": "eng Premier League", "it ITA": "it Serie A", "de GER": "de Bundesliga",
           "fr FRA": "fr Ligue 1", "es ESP": "es La Liga"}
IDENTITY = {"Rk", "Player", "Nation", "Pos", "Squad", "Comp", "Age", "Born"}
TEXT = {"Squad", "Country", "Top Team Scorer", "Goalkeeper"}


def digest(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def numeric(value):
    if not value:
        return None
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value):
        raise ValueError(f"Invalid numeric cell {value!r}")
    return float(value) if "." in value else int(value)


def parse_csv(data, subject, schema):
    rows = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    header = next(rows)
    if subject != "Clubs":
        header = [f"{group}.{name}" if group and name else name
                  for group, name in zip(header, next(rows), strict=True)]
    if header != schema:
        raise ValueError(f"{subject}: unexpected columns")
    for number, row in enumerate(rows, 2 if subject == "Clubs" else 3):
        if len(row) != len(header) or any(v for k, v in zip(header, row) if not k):
            raise ValueError(f"{subject} row {number}: malformed row")
        yield number, {k: v.strip() for k, v in zip(header, row) if k}


def publish(folder, season, url=None, market=None, acquired=None, mappings=None):
    schemas = json.loads(Path(__file__).with_name("headers.json").read_text())
    sources = {}
    for subject in SUBJECTS:
        label = "Clubs" if subject == "Clubs" else f"Player {subject}"
        matches = list(Path(folder).glob(f"{season} {label} Big 5*.csv"))
        if len(matches) != 1:
            raise ValueError(f"Expected one {label} file for {season}")
        sources[subject] = matches[0]
    if market:
        sources["market"] = Path(market)
    if mappings:
        sources["mappings"] = Path(mappings)
    batch = {k: p.read_bytes() for k, p in sources.items()}
    hashes = {k: hashlib.sha256(v).hexdigest() for k, v in batch.items()}
    snapshot = digest(VERSION, season, hashes, acquired)
    with database(url, importing=True) as db:
        if not db.run("SELECT 1 FROM snapshot WHERE id=?", (snapshot,)).fetchone():
            db.insert("season", [(season,)], existing=True)
            db.insert("snapshot", [(snapshot, season, VERSION)])
            db.insert("source_file", [(snapshot,k,p.name,hashes[k]) for k,p in sources.items()])
            clubs = {}
            for line, r in parse_csv(batch["Clubs"], "Clubs", schemas["Clubs"]):
                comp = LEAGUES[r["Country"]]
                club = digest(r["Country"], r["Squad"])
                clubs[comp,r["Squad"]] = club
                db.insert("competition", [(comp,r["Country"])], existing=True)
                db.insert("club", [(club,r["Squad"],r["Country"])], existing=True)
                stats = {k:v if k in TEXT else numeric(v) for k,v in r.items()}
                db.insert("club_season", [(snapshot,club,comp,line,json.dumps(stats))])
            observations = defaultdict(dict)
            for subject in SUBJECTS[1:]:
                for line, row in parse_csv(batch[subject], subject, schemas[subject]):
                    key = tuple(row[k] for k in ("Player","Born","Comp","Squad"))
                    if subject in observations[key]:
                        raise ValueError(f"Duplicate {subject} key {key}")
                    observations[key][subject] = line,row
            if any(not any(s in records for records in observations.values()) for s in SUBJECTS[1:]):
                raise ValueError("Empty subject")
            subject_keys = {subject: {key for key, records in observations.items() if subject in records}
                            for subject in SUBJECTS[1:]}
            standard = subject_keys["Standard Stats"]
            if any(subject_keys[other] != standard for other in ("Shooting","Miscellaneous Stats")):
                raise ValueError("Incomplete performance coverage relative to Standard Stats")
            if not subject_keys["Goalkeeping"] <= standard or not standard <= subject_keys["Playing Time"]:
                raise ValueError("Goalkeeping or Playing Time coverage differs from the declared export layout")
            players, stints, metrics, candidates = {}, [], [], []
            for key, records in observations.items():
                name,born,comp,squad = key
                base = records.get("Standard Stats", next(iter(records.values())))[1]
                nation = base["Nation"]
                club = clubs[comp,squad]
                # Exact birth year and nationality corroborate cross-club names.
                identity = digest(name,born,nation) if born and nation else digest(season,*key)
                players[identity] = (identity,name,numeric(born))
                stint = digest(snapshot,*key)
                minutes = base.get("Playing Time.Min","")
                stints.append((stint,snapshot,identity,club,comp,base["Pos"],nation,numeric(base["Age"]),numeric(minutes)))
                candidates.append((identity,name,born,squad,comp))
                for subject,(line,row) in records.items():
                    stats = {k:numeric(v) for k,v in row.items() if k not in IDENTITY}
                    for field in ("Pos","Nation","Age","Playing Time.Min","Performance.Gls"):
                        if row.get(field) and base.get(field) and row[field] != base[field]:
                            stats.setdefault("_discrepancies",{})[field] = row[field]
                    metrics.append((stint,subject,line,json.dumps(stats)))
            db.insert("player", players.values(), existing=True)
            db.insert("stint", stints)
            db.insert("performance", metrics)
            for subject in SUBJECTS[1:]:
                facts = [(stint, source, field, value)
                         for stint, source, _, payload in metrics if source == subject
                         for field, value in json.loads(payload).items()
                         if field != "_discrepancies" and value is not None]
                db.insert("measurement", facts)
            if db.postgres:
                from .quality import reconcile
                reconcile(db, snapshot, observations, metrics)
            if market:
                import_market(db,snapshot,season,batch["market"],acquired,candidates,batch.get("mappings"))
        db.run("INSERT INTO active_snapshot VALUES (?,?) ON CONFLICT(season) DO UPDATE SET snapshot=excluded.snapshot",(season,snapshot))
    return snapshot


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--data", default="External Files")
    args.add_argument("--season", default="2025-2026")
    args.add_argument("--market")
    args.add_argument("--acquired", help="Actual offline market export date (YYYY-MM-DD)")
    args.add_argument("--mappings", help="Reviewed JSON identity map keyed by Transfermarkt ID")
    options = args.parse_args()
    print(publish(options.data, options.season, market=options.market, acquired=options.acquired, mappings=options.mappings))
