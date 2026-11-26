CREATE TABLE IF NOT EXISTS season (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS competition (id TEXT PRIMARY KEY, country TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS club (id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL, UNIQUE(name,country));
CREATE TABLE IF NOT EXISTS snapshot (id TEXT PRIMARY KEY, season TEXT NOT NULL REFERENCES season, version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS active_snapshot (season TEXT PRIMARY KEY REFERENCES season, snapshot TEXT NOT NULL REFERENCES snapshot);
CREATE TABLE IF NOT EXISTS source_file (snapshot TEXT REFERENCES snapshot, subject TEXT, filename TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(snapshot,subject));
CREATE TABLE IF NOT EXISTS club_season (snapshot TEXT REFERENCES snapshot, club TEXT REFERENCES club, competition TEXT REFERENCES competition, source_row INTEGER NOT NULL, stats TEXT NOT NULL, PRIMARY KEY(snapshot,club));
CREATE TABLE IF NOT EXISTS player (id TEXT PRIMARY KEY, name TEXT NOT NULL, born INTEGER);
CREATE TABLE IF NOT EXISTS stint (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL REFERENCES snapshot, player TEXT NOT NULL REFERENCES player, club TEXT NOT NULL REFERENCES club, competition TEXT NOT NULL REFERENCES competition, position TEXT, nation TEXT, age INTEGER, minutes INTEGER, UNIQUE(snapshot,player,club,competition), FOREIGN KEY(snapshot,club) REFERENCES club_season(snapshot,club));
CREATE TABLE IF NOT EXISTS performance (stint TEXT REFERENCES stint, subject TEXT, source_row INTEGER NOT NULL, stats TEXT NOT NULL, PRIMARY KEY(stint,subject));
CREATE TABLE IF NOT EXISTS market_profile (snapshot TEXT REFERENCES snapshot, external_id TEXT, player TEXT REFERENCES player, decision TEXT NOT NULL, evidence TEXT NOT NULL, source_row INTEGER NOT NULL, PRIMARY KEY(snapshot,external_id), UNIQUE(snapshot,player));
CREATE TABLE IF NOT EXISTS valuation (snapshot TEXT, external_id TEXT, effective TEXT, currency TEXT, amount BIGINT NOT NULL CHECK(amount>=0), original TEXT NOT NULL, acquired TEXT NOT NULL, PRIMARY KEY(snapshot,external_id,effective,currency), FOREIGN KEY(snapshot,external_id) REFERENCES market_profile);
CREATE INDEX IF NOT EXISTS stint_lookup ON stint(snapshot,position,minutes);
CREATE INDEX IF NOT EXISTS value_lookup ON valuation(snapshot,external_id,effective);

CREATE TABLE IF NOT EXISTS measurement (
    stint TEXT NOT NULL, subject TEXT NOT NULL, field TEXT NOT NULL, value DOUBLE PRECISION NOT NULL,
    PRIMARY KEY(stint,subject,field), FOREIGN KEY(stint,subject) REFERENCES performance(stint,subject)
);
