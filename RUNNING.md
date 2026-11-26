# Run the recruitment desk

Start in the platform checkout (the directory containing compose.yaml). Originals under External Files and the adjacent scraper samples are read-only inputs.

## Already built locally on Windows

From the workspace root run the following in PowerShell. Open http://127.0.0.1:8000 and leave the terminal open. Ctrl+C stops the preview.

```powershell
cd ".\Football-Transfer-Investment-Analytics-Platform"
python -m scouting.local
```

The populated local SQL file is scouting.sqlite3 beside this guide. Docker Compose uses a separate PostgreSQL database named scouting, stored in the scouting_data volume.

## Local Compose

Copy .env.example to .env and set a private, URL-safe POSTGRES_PASSWORD. Run:

```sh
docker compose up --build
```

Open http://localhost:8000 for the React desk and /docs for FastAPI's interactive API. The import service creates the schema, validates the six files, stages the bundled market sample and publishes the snapshot before startup. Re-run the import service after an input change. PostgreSQL retains earlier snapshots in the named volume. The application serializes publishers with a transaction advisory lock. Source content, season, parser version and market acquisition date determine the snapshot ID.

## Local preview without containers

Python 3.11+ supports a SQLite preview with the same schema, importer and scoring functions. In the checkout:

```sh
python -m scouting.ingest --market ../transfermarkt-scraper/samples/players.json
python -m scouting.engine --role MF --max-age 23 --minutes 900 --limit 5
cd frontend
npm ci
npm run build
cd ..
python -m scouting.local
```

Open http://127.0.0.1:8000. Preview data lives in the ignored scouting.sqlite3 file. Set DATABASE_URL to a PostgreSQL connection URI for the primary backend or a file path for SQLite. For backend development install requirements.txt in a project virtual environment and run uvicorn scouting.api:app --reload. In VS Code launch module scouting.ingest or scouting.engine with this directory as cwd. Break at publish to inspect parsing, or rank to inspect the cohort before filters.

## Using scores

The result unit is a player’s stint at one club in one competition and season. Select a primary position (the first position in the source), minimum minutes and role weights. The ranker uses all qualifying stints at that position across the five leagues. Each feature uses its own observed peers. Three observations are required. Average tied ranks map to 0–100; lower goals conceded is better. The weighted mean requires complete weighted feature coverage. Changing age, name, league, price or page preserves the underlying peer rankings. Weights need a positive total and need not sum to 100. The role score measures suitability under those choices. Minutes and cohort size help interpret sparse evidence.

POST /api/v1/rankings accepts role, season, weights, minutes, min_age, max_age, budget, currency, as_of, search, league, offset and limit. GET /api/v1/roles exposes presets and metric labels. For example:

```json
{"role":"MF","weights":{"assists":2,"interceptions":1},"minutes":900,"max_age":23,"limit":10}
```

Choose position, league and player from dropdowns. Use the sliders for age, minutes, market value, per-90 production and tactical weights. Choose Search to apply the draft criteria. Outfield per-90 filters use the published FBref rates for all goals, assists and shots. Decimal bands end at 1.00+. Tactical weights set scoring importance independently. Each card shows the latest available market estimate beside role fit, plus the actual stint totals. Expand a result to see its source measurements, percentiles and points. Keep an eye on the cohort count when adjusting minutes. The desk automatically displays the latest known matched market estimate in its original currency. The valuation date is informational. Choosing a price band excludes missing estimates and other currencies. The API retains an optional historical cutoff for reproducible queries. Cutoffs apply to market evidence; FBref measures always represent the full imported season.

## Market evidence and identity review

The bundled player profile is historical and contains no valuation. A budget query on the supplied data returns zero candidates. Import further offline player JSONL with --market PATH --acquired YYYY-MM-DD, using the actual acquisition date. A current estimate such as a currency symbol followed by a number and optional k/m/bn suffix is dated to acquisition. Historical entries supported by this adapter have an ISO date and currency-bearing value string. Unknown formats reject the whole batch. Preserve the original export when converting other chart formats offline.

Inspect market_profile.evidence for candidate IDs. A reviewer must corroborate the player's identity using birth and membership evidence before a price can be attached. Supply --mappings PATH with JSON keyed by numeric Transfermarkt ID. Each entry requires player_id, reviewer, reviewed_on (ISO date) and evidence. Reuse this mapping file on subsequent imports; its hash is part of the snapshot. Unapproved market observations remain separate and ineligible for budget filtering.

FBref has no stable player ID. The importer groups exact name, birth year and nationality across clubs; missing birth or nationality keeps an observation scoped to its season and club. This is a deterministic working identity. Same-name, same-year, same-nationality people can collide, and spelling/nationality changes can split records. Stint details and subject provenance remain available even across transfers. Compare identities before approving an external link.

## Verification

```sh
python -m unittest discover -s tests -v
cd frontend
npm ci
npm run build
```

Tests use temporary databases, real CSVs, the existing profile sample and an isolated budget-boundary fixture. PostgreSQL adds a Pandas reconciliation check before publishing. Inspect source_file for hashes, club_season for club results, performance for original grouped statistics and row numbers, measurement for typed nonmissing scalar observations, and active_snapshot for the published version.
