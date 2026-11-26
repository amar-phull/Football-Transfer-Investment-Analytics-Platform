declare const ReactDOM: typeof import("react-dom/client");
const { useEffect, useState } = React;

type Weights = Record<string, number>;

interface Profiles {
  profiles: Record<string, Weights>;
  labels: Record<string, string>;
}

interface Metric {
  label: string;
  value: number;
  percentile?: number;
  contribution?: number;
  source: string;
  row: number;
}

interface Player {
  stint: string;
  name: string;
  club: string;
  competition: string;
  position: string;
  age: number | null;
  minutes: number;
  score: number | null;
  valuation: { amount: number; currency: string; date: string; source: string } | null;
  metrics: Record<string, Metric>;
  stats: Record<string, number | null>;
}

interface ResultsPage {
  cohort: number;
  total: number;
  valued: number;
  results: Player[];
}

type Band = [label: string, minimum: number | null, maximum: number | null];

const AGE_BANDS: Band[] = [
  ["All ages", null, null],
  ["Under 18", null, 17],
  ["18–21", 18, 21],
  ["22–25", 22, 25],
  ["26–29", 26, 29],
  ["30 and over", 30, null],
];

const MINUTES_BANDS: Band[] = [
  ["Any playing time", 1, null],
  ["450 or more", 450, null],
  ["1–449", 1, 449],
  ["450–899", 450, 899],
  ["900–1,799", 900, 1799],
  ["1,800 or more", 1800, null],
];

const BUDGET_BANDS: Band[] = [
  ["Any value", null, null],
  ["Up to 5 million", null, 5_000_000],
  ["Over 5 to 15 million", 5_000_001, 15_000_000],
  ["Over 15 to 30 million", 15_000_001, 30_000_000],
  ["Over 30 to 60 million", 30_000_001, 60_000_000],
  ["Over 60 million", 60_000_001, null],
];

const RATE_LABELS = [
  "Any rate", "0.00–0.09", "0.10–0.24", "0.25–0.49",
  "0.50–0.74", "0.75–0.99", "1.00+",
];
const LEAGUES = ["eng Premier League", "es La Liga", "de Bundesliga", "it Serie A", "fr Ligue 1"];
const POSITIONS = { FW: "Forward", MF: "Midfielder", DF: "Defender", GK: "Goalkeeper" };
const PAGE_SIZE = 25;

function leagueName(competition: string) {
  return competition.substring(competition.indexOf(" ") + 1);
}

const WEIGHT_LABELS = Array.from({ length: 11 }, (_, weight) =>
  weight === 0 ? "Off" : weight + " / 10"
);

interface CriteriaSliderProps {
  label: string;
  options: string[];
  index: number;
  onChange: (index: number) => void;
}

function CriteriaSlider({ label, options, index, onChange }: CriteriaSliderProps) {
  return (
    <label className="criteria-slider">
      <span className="slider-heading">
        <span>{label}</span>
        <strong aria-hidden="true">{options[index]}</strong>
      </span>
      <input
        type="range"
        min={0}
        max={options.length - 1}
        step={1}
        value={index}
        aria-valuetext={options[index]}
        onChange={event => onChange(event.currentTarget.valueAsNumber)}
      />
    </label>
  );
}

function FormationPicker({ role, onSelect }: { role: string; onSelect: (role: string) => void }) {
  return (
    <div className="formation" role="group" aria-label="Select search position">
      <div className="pitch">
        <i className="box left" /><i className="box right" /><i className="circle" />
        {Object.entries(POSITIONS).map(([code, name]) => (
          <button key={code} type="button" className={"marker marker-" + code}
            aria-label={"Select " + name} aria-pressed={role === code} onClick={() => onSelect(code)}>
            {code}
          </button>
        ))}
      </div>
      <small>Select a position on the pitch</small>
    </div>
  );
}

function Comparison({ players }: { players: Player[] }) {
  const labels = Array.from(new Set(players.flatMap(player => Object.keys(player.stats))));
  return (
    <div className="comparison">
      <h3>Stint comparison</h3>
      <div className="table-scroll">
        <table>
          <thead><tr><th scope="col">Statistic</th>{players.map(player => (
            <th key={player.stint} scope="col">{player.name}<small>{player.club}</small></th>
          ))}</tr></thead>
          <tbody>
            {["Minutes", ...labels].map(label => (
              <tr key={label}><th scope="row">{label}</th>
                {players.map(player => {
                  const value = label === "Minutes" ? player.minutes : player.stats[label];
                  return <td key={player.stint}>{value == null ? "—" : value.toLocaleString()}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface PlayerCardProps {
  player: Player;
  saved: boolean;
  onToggleSaved: () => void;
}

function PlayerCard({ player, saved, onToggleSaved }: PlayerCardProps) {
  const { valuation } = player;
  const marketValue = valuation
    ? new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: valuation.currency,
        maximumFractionDigits: 0,
      }).format(valuation.amount)
    : "Unavailable";

  return (
    <article className="player-card">
      <button className="save" aria-pressed={saved} onClick={onToggleSaved}>
        {saved ? "Saved" : "Save"}
      </button>
      <span className="position-tag">{player.position}</span>
      <h3>{player.name}</h3>
      <p>{player.club} · {leagueName(player.competition)} · {player.position} · Age {player.age ?? "unknown"}</p>

      <div className="headline">
        <div>
          Role fit
          <strong>{player.score?.toFixed(1) ?? "—"} <small>/ 100</small></strong>
        </div>
        <div>
          Market value
          <strong>{marketValue}</strong>
          {valuation && <small>{valuation.source} · {valuation.date}</small>}
        </div>
      </div>

      <div className="stat-strip">
        {["Minutes", ...(player.position.startsWith("GK")
          ? ["Saves", "Save %", "Clean sheets"] : ["Goals / 90", "Assists / 90", "Shots / 90"])].map(label => {
          const value = label === "Minutes" ? player.minutes : player.stats[label];
          return (
            <div key={label}><small>{label}</small>
              <b>{value == null ? "—" : label.endsWith("/ 90") ? value.toFixed(2) : value.toLocaleString()}</b>
            </div>
          );
        })}
      </div>
      <details>
        <summary>Full statistics</summary>
        <dl>{Object.entries(player.stats).map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd>{value ?? "—"}</dd></div>
        ))}</dl>
      </details>

      <details>
        <summary>Score breakdown</summary>
        {Object.entries(player.metrics).map(([key, metric]) => (
          <p key={key}>
            <meter min={0} max={100} value={metric.percentile ?? 0} aria-label={metric.label + " percentile"} />
            {metric.label} <b>{metric.value.toFixed(2)}</b>
            {" · percentile "}{metric.percentile?.toFixed(1) ?? "—"}
            {" · "}{metric.contribution?.toFixed(1) ?? "—"} points
            {" · "}{metric.source}, row {metric.row}
          </p>
        ))}
      </details>
    </article>
  );
}

function Desk() {
  const [profiles, setProfiles] = useState<Profiles>();
  const [playerNames, setPlayerNames] = useState<string[]>([]);
  const [criteriaError, setCriteriaError] = useState("");

  const [role, setRole] = useState("FW");
  const [weights, setWeights] = useState<Weights | null>(null);
  const [rateBands, setRateBands] = useState<Record<string, number>>({});
  const [ageBand, setAgeBand] = useState(0);
  const [minutesBand, setMinutesBand] = useState(1);
  const [budgetBand, setBudgetBand] = useState(0);
  const [currency, setCurrency] = useState("EUR");
  const [league, setLeague] = useState("");
  const [playerName, setPlayerName] = useState("");

  // Pagination uses the last submitted criteria while the form holds draft edits.
  const [submitted, setSubmitted] = useState<Record<string, unknown>>({
    role: "FW", minutes: 450, limit: PAGE_SIZE,
  });
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<ResultsPage>();
  const [searchError, setSearchError] = useState("");
  const [shortlist, setShortlist] = useState<Player[]>(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("recruitment.shortlist.v1") ?? "[]");
      return Array.isArray(stored) ? stored.filter(player => player?.stint && player.stats && player.metrics) : [];
    } catch {
      return [];
    }
  });
  const [compareIds, setCompareIds] = useState<string[]>([]);
  useEffect(() => {
    try {
      localStorage.setItem("recruitment.shortlist.v1", JSON.stringify(shortlist));
    } catch {
      // Browsers that disable storage still support an in-session shortlist.
    }
  }, [shortlist]);
  const [onlySaved, setOnlySaved] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    async function loadCriteria() {
      const endpoints = ["/api/v1/roles", "/api/v1/names"];
      const [profiles, names] = await Promise.all(endpoints.map(async url => {
        const response = await fetch(url);
        if (!response.ok) throw Error("Could not load selection criteria.");
        return response.json();
      }));
      setProfiles(profiles);
      setPlayerNames(names);
    }
    loadCriteria().catch(error => setCriteriaError(error.message));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setPage(undefined);
    setSearchError("");

    async function loadRankings() {
      const response = await fetch("/api/v1/rankings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...submitted, offset }),
        signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok) {
        throw Error(typeof result.detail === "string" ? result.detail : "Check selection criteria.");
      }
      if (!controller.signal.aborted) setPage(result);
    }

    loadRankings().catch(error => {
      if (!controller.signal.aborted) setSearchError(error.message);
    });
    return () => controller.abort();
  }, [submitted, offset]);

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    const [, minAge, maxAge] = AGE_BANDS[ageBand];
    const [, minMinutes, maxMinutes] = MINUTES_BANDS[minutesBand];
    const [, minBudget, maxBudget] = BUDGET_BANDS[budgetBand];

    setOnlySaved(false);
    setFiltersOpen(false);
    setOffset(0);
    setSubmitted({
      role, weights, currency, league,
      minutes: minMinutes,
      max_minutes: maxMinutes,
      min_age: minAge,
      max_age: maxAge,
      min_budget: minBudget,
      budget: maxBudget,
      player_name: playerName,
      rate_bands: role === "GK" ? {} : rateBands,
      limit: PAGE_SIZE,
    });
  }

  function resetCriteria() {
    setRole("FW");
    setWeights(null);
    setRateBands({});
    setAgeBand(0);
    setMinutesBand(1);
    setBudgetBand(0);
    setCurrency("EUR");
    setLeague("");
    setPlayerName("");
    setOnlySaved(false);
  }

  function changeRateBand(metric: string, index: number) {
    const next = { ...rateBands };
    if (index < 0) delete next[metric];
    else next[metric] = index;
    setRateBands(next);
  }

  function toggleSaved(player: Player) {
    setShortlist(current => current.some(item => item.stint === player.stint)
      ? current.filter(item => item.stint !== player.stint) : [...current, player]);
    setCompareIds(current => current.filter(id => id !== player.stint));
  }

  function choosePosition(nextRole: string) {
    setRole(nextRole);
    setWeights(null);
  }

  const activeWeights = weights ?? profiles?.profiles[role] ?? {};
  const roleMetrics = Object.entries(profiles?.labels ?? {}).filter(([key]) => {
    const goalkeeperMetric = key === "saves" || key === "conceded";
    return goalkeeperMetric === (role === "GK");
  });
  const visiblePlayers = onlySaved ? shortlist : page?.results ?? [];
  const comparison = shortlist.filter(player => compareIds.includes(player.stint));
  const hasBudgetFilter = submitted.budget != null || submitted.min_budget != null;

  return (
    <main>
      <header className="masthead">
        <div className="topbar">
          <strong className="wordmark"><i aria-hidden="true" /> Touchline</strong>
          <span>Football recruitment</span>
        </div>
        <div className="hero">
          <div><span className="season">Big Five leagues · 2025–26</span>
            <h1>Recruitment <em>desk.</em></h1>
            <nav className="views" aria-label="Workspace views">
              <button aria-pressed={!onlySaved} onClick={() => setOnlySaved(false)}>Scout players</button>
              <button aria-pressed={onlySaved} onClick={() => setOnlySaved(true)}>Shortlist <b>{shortlist.length}</b></button>
            </nav>
          </div>
          <FormationPicker role={role} onSelect={nextRole => { choosePosition(nextRole); setFiltersOpen(true); }} />
        </div>
      </header>

      <div className="layout">
        <aside>
          <button className="filter-toggle" aria-expanded={filtersOpen} aria-controls="search-form"
            onClick={() => setFiltersOpen(!filtersOpen)}>
            {filtersOpen ? "Close criteria" : "Adjust search criteria"}
          </button>
          <form id="search-form" className={filtersOpen ? "filters-open" : ""} onSubmit={submitSearch}>
            <h2>Selection criteria</h2>
            <label>
              Position
              <select value={role} onChange={event => choosePosition(event.target.value)}>
                {Object.entries(POSITIONS).map(([code, label]) => (
                  <option key={code} value={code}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              League
              <select value={league} onChange={event => setLeague(event.target.value)}>
                <option value="">All five leagues</option>
                {LEAGUES.map(name => <option key={name} value={name}>{leagueName(name)}</option>)}
              </select>
            </label>
            <label>
              Player
              <select value={playerName} onChange={event => setPlayerName(event.target.value)}>
                <option value="">All players</option>
                {playerNames.map(name => <option key={name}>{name}</option>)}
              </select>
            </label>

            <CriteriaSlider
              label="Age range"
              options={AGE_BANDS.map(([label]) => label)}
              index={ageBand}
              onChange={setAgeBand}
            />
            <CriteriaSlider
              label="Minutes played"
              options={MINUTES_BANDS.map(([label]) => label)}
              index={minutesBand}
              onChange={setMinutesBand}
            />
            <CriteriaSlider
              label="Market value range"
              options={BUDGET_BANDS.map(([label]) => label)}
              index={budgetBand}
              onChange={setBudgetBand}
            />

            {budgetBand > 0 && (
              <label>
                Budget currency
                <select value={currency} onChange={event => setCurrency(event.target.value)}>
                  {["EUR", "GBP", "USD"].map(unit => <option key={unit}>{unit}</option>)}
                </select>
              </label>
            )}

            {role !== "GK" && (
              <fieldset>
                <legend>Production per 90 minutes</legend>
                {["goals", "assists", "shots"].map(metric => (
                  <CriteriaSlider
                    key={metric}
                    label={metric[0].toUpperCase() + metric.slice(1) + " / 90"}
                    options={RATE_LABELS}
                    index={(rateBands[metric] ?? -1) + 1}
                    onChange={index => changeRateBand(metric, index - 1)}
                  />
                ))}
              </fieldset>
            )}

            <details>
              <summary>Tactical weights</summary>
              {roleMetrics.map(([key, label]) => (
                <CriteriaSlider
                  key={key}
                  label={label}
                  options={WEIGHT_LABELS}
                  index={activeWeights[key] ?? 0}
                  onChange={weight => setWeights({ ...activeWeights, [key]: weight })}
                />
              ))}
            </details>

            <nav>
              <button type="submit">Search</button>
              <button type="button" onClick={resetCriteria}>Reset criteria</button>
            </nav>
          </form>
          {criteriaError && <p role="alert">{criteriaError}</p>}
        </aside>

        <section>
          <h2>{onlySaved ? "Your shortlist" : "Scouting results"}</h2>
          <details className="guide">
            <summary>Where market values come from</summary>
            <p>
              The desk uses the latest imported Transfermarkt estimate linked to a reviewed player identity.
              Values appear in the original currency. Applying a value range requires a matching currency.
              The bundled profile has no estimate.
            </p>
          </details>

          {!onlySaved && searchError && <p role="alert">{searchError}</p>}
          {!onlySaved && !page && !searchError && <p role="status">Loading candidates…</p>}
          {(onlySaved || (page && !searchError)) && (
            <>
              {!onlySaved && page && (
                <div className="summary-strip" aria-live="polite">
                  <div><strong>{page.total}</strong><span>Matching stints</span></div>
                  <div><strong>{page.cohort}</strong><span>Positional peers</span></div>
                  <div><strong>{page.valued}</strong><span>With a valuation</span></div>
                </div>
              )}
              {onlySaved && (
                <p className="hint">{shortlist.length
                  ? "Select up to three stints to compare. Each card retains the role score from the search where you saved it."
                  : "Save a candidate from scouting results to start your shortlist."}</p>
              )}
              {onlySaved && comparison.length >= 2 && <Comparison players={comparison} />}

              <div className="card-grid">
                {visiblePlayers.map(player => (
                  <div className="card-wrap" key={player.stint}>
                    {onlySaved && (
                      <label className="compare-choice">
                        <input type="checkbox" checked={compareIds.includes(player.stint)}
                          disabled={compareIds.length >= 3 && !compareIds.includes(player.stint)}
                          onChange={event => setCompareIds(event.target.checked
                            ? [...compareIds, player.stint] : compareIds.filter(id => id !== player.stint))} />
                        Compare {player.name}
                      </label>
                    )}
                    <PlayerCard player={player} saved={shortlist.some(item => item.stint === player.stint)}
                      onToggleSaved={() => toggleSaved(player)} />
                  </div>
                ))}
              </div>

              {!onlySaved && page?.total === 0 && (
                <p>
                  No candidates meet these criteria.
                  {hasBudgetFilter && " Choose Any value to include players without a matched estimate."}
                </p>
              )}
              {!onlySaved && page && <nav className="pagination">
                <button disabled={!offset} onClick={() => setOffset(offset - PAGE_SIZE)}>Previous</button>
                <span>{page.total ? offset + 1 : 0}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}</span>
                <button disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)}>
                  Next
                </button>
              </nav>}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<Desk />);
