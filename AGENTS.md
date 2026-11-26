# AGENTS.md — Football Transfer Investment Analytics Platform

## Purpose
Build a maintainable, explainable **football recruitment decision engine** using real football performance data and market-value observations. The product should help a user identify and compare transfer targets according to **tactical fit, performance, budget, relative value, and evidence-backed risk indicators**.

The decision engine is **not** a universal player-rating system or a tool that can guarantee transfer success or investment returns. Explain why a candidate ranks highly, show the underlying metrics, and distinguish observed data from estimates and heuristics.

## Current workspace and source-of-truth rules
- The workspace contains FBref-derived CSV files for the 2025–26 Big Five European leagues, including player standard, shooting, miscellaneous, playing-time and goalkeeping statistics, plus club statistics. Inspect actual files and columns before making assumptions.
- The workspace also contains a locally added Transfermarkt scraper GitHub repository. Treat it as **third-party code**. Inspect its README, licence, interfaces and output schemas before proposing integration. Its presence does **not** imply that scraped valuations already exist.
- Preserve all original CSVs, existing source files, and scraper history. Do not edit or delete raw datasets. Put derived data in separate locations.
- Do not assume CSV files have standard single-row headers, unique column names, stable player IDs, complete values, or identical row granularity. Verify each assumption by inspection.
- A player's name alone is not a reliable join key. Design explicit entity resolution, record provenance and confidence, and flag ambiguous matches for review instead of silently merging them.
- Distinguish player-season, player-club-season and club-season observations; account for players appearing at multiple clubs in a season.
- Transfermarkt **market value estimates are not actual transfer fees**. Never label an estimated market value as a realised transaction price.

## Working method: inspect → plan → implement → verify
1. **Inspect first.** Before changing code, read the relevant files, identify the existing architecture, and describe the task's dependencies and data requirements.
2. **Plan nontrivial changes.** Maintain `PROJECT_PLAN.md` with phases, acceptance criteria, data gaps, decisions and status. For the initial discovery request, produce the plan and **stop before implementing application code**.
3. **Implement incrementally.** Prefer small, reviewable changes with clear boundaries. Do not generate a huge unverified application in one pass.
4. **Verify every change.** Run focused tests, type checks and linting where available. Report commands executed and results. Never claim tests passed unless they were run.
5. **Explain decisions.** Summarise what changed, why, alternatives considered, remaining risks, and how to run or debug the feature in VS Code.
6. **Escalate blockers.** Ask for clarification when requirements, data access, player matching, evaluation design or external permissions materially affect correctness.

## Product scope and priorities
Prioritise a useful, working MVP over speculative features:
1. Reproducible ingestion, profiling and cleaning of existing CSVs.
2. A coherent PostgreSQL schema and reliable import pipeline.
3. Player search and filters: position/role, league, age, minutes and budget **when valuations are available**.
4. Explainable, configurable tactical-fit scoring using position/role-relevant peer groups.
5. Ranking that balances tactical fit, observed performance, relative value and clearly defined risk indicators.
6. FastAPI endpoints and a React/TypeScript dashboard exposing score breakdowns and source metrics.
7. Player similarity with appropriate preprocessing and evaluation.
8. Optional valuation modelling, caching and further infrastructure only after the underlying data and use case justify them.

## Analytics and modelling rules
- Use **only metrics actually present** in inspected data or subsequently sourced and documented. Do not invent xG, xA, pressing events, injury histories, valuations, transfer fees, expected ROI, probabilities or benchmark results.
- Label indirect measures as **proxies**. For example, tackles and interceptions are not direct measures of pressing intensity or pressing success.
- Avoid raw cross-position comparisons. Use appropriate peer groups, minutes thresholds and transparent normalisation. Record how small samples and missing metrics affect rankings.
- Make tactical weights configurable and documented; validate inputs and explain the contribution of each feature to a recommendation.
- Keep **playing-style similarity** distinct from **price filtering**. Market value should not automatically dominate a similarity calculation.
- For similarity modelling, use a reproducible feature set, sensible scaling, documented missing-value handling and interpretable distance/similarity metrics. scikit-learn is optional until there is a concrete need.
- A heuristic **risk indicator** is not a calibrated probability of transfer failure. Show its components and limitations. Do not invent injury or adaptation risk data.
- Do not claim a player is definitively "undervalued". Prefer "potentially undervalued relative to the selected metrics, peer group or model".
- Do not claim **future ROI** without time-indexed historical outcomes and a defensible evaluation methodology. A model predicting contemporary market value does not predict future appreciation.
- If valuation ML is justified, establish simple baselines, prevent target leakage, use appropriate time-based or group-aware splits, and report MAE/RMSE plus limitations. Never present training-set fit as out-of-sample performance.
- Keep calculations deterministic and testable where practical; fix random seeds for stochastic experiments and record feature definitions.

## Architecture and engineering preferences
- Preferred stack, subject to repository inspection: **Python, Pandas, PostgreSQL, FastAPI, React, TypeScript, Docker Compose**; use scikit-learn for justified analytics/ML tasks.
- Start with a **modular monolith**, not microservices. Separate ingestion, domain models, scoring/analytics, persistence, API schemas/routes and frontend presentation.
- Keep business logic independent of FastAPI route handlers and database access details. Avoid implementing scoring rules in React components.
- Prefer straightforward dependencies and explicit interfaces. Do not add Redis, XGBoost, Celery, Kubernetes or cloud infrastructure merely to make the stack look impressive.
- Use migrations for schema changes, typed interfaces where appropriate, configuration through environment variables, and `.env.example` with no secrets.
- Use stable identifiers, foreign keys, uniqueness constraints and indexes based on real query patterns. Imports should be **idempotent** and preserve data provenance.
- Expose consistent, versionable REST endpoints with input validation, pagination, meaningful errors and OpenAPI documentation.
- Build accessible, responsive UI states for loading, empty results, missing data and failures. Show observed vs estimated values distinctly.
- Add Redis only after measuring a meaningful repeated-query bottleneck; report before/after latency and invalidation strategy.
- Add Docker Compose for reproducible local development once the core services are ready. CI should run meaningful automated checks.

## Repository organisation
Adapt to existing conventions rather than moving files unnecessarily. A possible structure is:

```text
data/raw/                  # Original source datasets: immutable
data/processed/            # Generated datasets: reproducible
third_party/ or existing scraper folder/  # External scraper, kept isolated
backend/app/ingestion/     # Source-specific parsing and import
backend/app/domain/        # Core entities and rules
backend/app/services/      # Scoring, ranking, similarity
backend/app/repositories/  # Persistence access
backend/app/api/           # FastAPI endpoints and schemas
backend/tests/             # Unit and integration tests
frontend/                  # React + TypeScript
PROJECT_PLAN.md            # Roadmap, decisions and phase gates
README.md                  # Setup and operating instructions
```

Do not rename or relocate the scraper repository without approval, especially if it is a nested Git repository or submodule.

## Testing and acceptance criteria
- Test CSV parsing against representative real input, including multi-row headers, duplicate names, missing values and numeric conversion.
- Test identity matching and ambiguous matches; test multi-club seasons and repeated imports.
- Test scoring with small hand-checkable fixtures, weights summing to expected totals, missing metrics, peer-group selection and minimum-minutes filtering.
- Test API validation, pagination, errors and key database queries.
- Where possible, run integration tests against a disposable local database, not a production or user-maintained database.
- Use regression tests for any discovered data-quality or ranking bugs.
- For each completed phase, provide: implemented features, files changed, commands run, tests/results, limitations, and next steps.

## Safety, permissions and external operations
- **Do not execute Transfermarkt/FBref scraping or other network collection without explicit approval.** Respect applicable site terms, licensing, robots policies and reasonable rate limits; do not bypass access controls or bot protections.
- Do not modify the third-party scraper source unless the user explicitly requests it. Prefer a separate adapter in this project.
- Do not delete/overwrite original files, rewrite Git history, run destructive database commands, or discard user changes.
- Do not commit, push, deploy, publish datasets, install system-wide tools, or access paid services without approval.
- Never print, commit or embed secrets, tokens, credentials or private configuration. Keep generated data and secrets appropriately ignored by Git.
- If a command fails, report the actual failure and fix its cause; do not silently skip tests or replace real data with fabricated values to make a demo work.

## Communication style
- Be precise, practical and candid about limitations. Prefer explaining trade-offs over adding complexity.
- Teach the architecture: for major changes explain the call flow, data flow, key modules, why the approach was chosen, and how to debug it with VS Code breakpoints/tests.
- Distinguish **implemented**, **tested**, **planned**, and **blocked** features in every progress summary.
- Keep CV-worthy claims factual: do not claim measured speedups, deployed infrastructure, trained models or working features until verified.
