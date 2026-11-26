import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scouting.db import database
from scouting.engine import rank
from scouting.ingest import publish, parse_csv
from scouting.market import money

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/"External Files"
MARKET = ROOT.parent/"transfermarkt-scraper/samples/players.json"
SEASON = "2025-2026"


class Platform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.url = str(Path(cls.tmp.name)/"test.sqlite3")
        with ThreadPoolExecutor(2) as workers:
            ids = list(workers.map(lambda _:publish(RAW,SEASON,cls.url,MARKET),range(2)))
        assert ids[0]==ids[1]
        cls.snapshot = ids[0]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_reconciliation(self):
        with database(self.url) as db:
            for table,n in (("snapshot",1),("club_season",96),("stint",3536),("valuation",0)):
                self.assertEqual(db.run(f"SELECT count(*) FROM {table}").fetchone()[0],n)
            counts=dict(db.run("SELECT subject,count(*) FROM performance GROUP BY subject"))
            self.assertEqual(counts,{"Goalkeeping":194,"Playing Time":3536,"Miscellaneous Stats":2839,"Shooting":2839,"Standard Stats":2839})
            self.assertEqual(db.run("SELECT count(*),count(distinct player) FROM stint JOIN player ON player.id=stint.player WHERE name='Himad Abdelli'").fetchone(),(2,1))
            self.assertEqual(db.run("SELECT external_id,decision FROM market_profile").fetchone(),("246968","review"))

    def test_rollback(self):
        corrupt = Path(self.tmp.name)/"broken.jsonl"
        corrupt.write_text("{")
        with self.assertRaises(ValueError):
            publish(RAW,SEASON,self.url,corrupt)
        with database(self.url) as db:
            self.assertEqual(db.run("SELECT snapshot FROM active_snapshot").fetchone()[0],self.snapshot)
            self.assertEqual(db.run("SELECT count(*) FROM snapshot").fetchone()[0],1)

    def test_schema_drift(self):
        for raw in (b"A,B\n1\n", b"B,A\n1,2\n"):
            with self.assertRaises(ValueError):
                list(parse_csv(raw,"Clubs",["A","B"]))

    def test_filters_after_percentiles(self):
        first = rank(url=self.url,max_age=22,limit=1)["results"][0]
        other = rank(url=self.url,search=first["name"])["results"]
        self.assertIn(first,other)
        self.assertAlmostEqual(sum(x["contribution"] for x in first["metrics"].values()),first["score"],places=3)
        self.assertEqual(rank(url=self.url,budget=100000000)["total"],0)
        gk = rank(url=self.url,role="GK",weights={"conceded":1})["results"]
        self.assertTrue(all(x["position"].startswith("GK") for x in gk))
        self.assertLessEqual(gk[0]["metrics"]["conceded"]["value"],gk[-1]["metrics"]["conceded"]["value"])

    def test_invalid_weights(self):
        for weights in ({},{"shots":0},{"saves":1},{"shots":-1},{"shots":float("nan")}):
            with self.assertRaises(ValueError):
                rank(url=self.url,weights=weights)

    def test_market_gate(self):
        # Isolated boundary fixture using the real sample identity and a test-only amount.
        with tempfile.TemporaryDirectory() as tmp:
            url=str(Path(tmp)/"market.sqlite3")
            sample=json.loads(MARKET.read_text(encoding="utf8"))
            sample["market_value_history"]=[{"date":"2025-06-01","value":"£2m"}]
            sample["current_market_value"]="€1.5m"
            export=Path(tmp)/"market.json"
            export.write_text(json.dumps(sample))
            with database(self.url) as db:
                pid=db.run("SELECT id FROM player WHERE name LIKE 'Ayoze P%' LIMIT 1").fetchone()[0]
            mapping=Path(tmp)/"review.json"
            mapping.write_text(json.dumps({"246968":{"reviewer":"test","reviewed_on":"2026-07-01","evidence":"isolated test fixture","player_id":pid}}))
            publish(RAW,SEASON,url,export,"2026-07-01",mapping)
            for cutoff,currency,budget,count in (("2026-06-30","EUR",1500000,0),("2026-07-01","GBP",1500000,0),("2026-07-01","EUR",1499999,0),("2026-07-01","EUR",1500000,1)):
                self.assertEqual(rank(url=url,minutes=1,budget=budget,as_of=cutoff,currency=currency)["total"],count)
            latest = rank(url=url,minutes=1,player_name="Ayoze Pérez",currency="GBP")["results"][0]
            self.assertEqual((latest["valuation"]["amount"],latest["valuation"]["currency"]),(1500000,"EUR"))
            self.assertEqual(rank(url=url,minutes=1,min_budget=1500001)["total"],0)
            with self.assertRaises(ValueError):
                money("undisclosed")
