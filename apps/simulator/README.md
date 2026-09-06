# apps/simulator

Stratified tank model plus synthetic draw profiles for a Croatian residential
electric water heater fleet. This exists so the state estimator and the bidding
logic can be validated offline, in minutes, instead of waiting for real days to
pass on one flat in Prečko.

Decision register: #56 (build the simulator first), #22, #24.

## Caveat on the numbers

The tank physics is standard thermodynamics and has been checked against an
independent hand calculation. **User behaviour is estimated, not measured** —
shower volumes, shower counts, the shape of the daily curve, holiday and
work-from-home patterns, archetype weights, and the thermostat probe position
are all assumptions. The probe position in particular is tuned to reproduce an
expected reheat duration, which is circular.

Shapes and relative differences between archetypes are credible. Absolute
figures are not, and must not enter a financial model on their own. See
`docs/05-sinteza.md` §9 for the per-figure reliability status.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Tests

```bash
pytest -m "not slow"     # ~25 s
pytest                   # includes full-year runs, minutes per test
```

## Generating the dataset

Output lands in `data/`, which is gitignored — all of it is reproducible from
here. Run from this directory.

```bash
# All archetypes, full year. Writes data/year_15min.csv.gz (~17 MB),
# data/year_events.csv.gz, data/year_summary.csv, data/metadata.json
python3 -m aquacell_sim.run_year

# One or more specific archetypes by id (A01 … A20, see archetypes.py)
python3 -m aquacell_sim.run_year A15 A20
```

## Analysis

Each takes an optional fleet size, default 5000. Requires the dataset above.

```bash
python3 -m aquacell_sim.analyse_year 5000          # per-archetype year summary
python3 -m aquacell_sim.analyse_fleet 5000 7       # fleet aggregation, seed 7
python3 -m aquacell_sim.analyse_windows 5000       # flexibility by hour window
python3 -m aquacell_sim.analyse_statistical 5000   # fleet percentile stability
```

Standalone experiments, no dataset needed:

```bash
python3 -m aquacell_sim.run_scenarios
python3 -m aquacell_sim.run_capacity_table
python3 -m aquacell_sim.run_risk_sweep
```

## Module map

| Module | Role |
|---|---|
| `tank.py` | 12-layer stratified tank: heater, advection, losses, conduction, buoyancy mixing |
| `draws.py` | Stochastic per-day draw generation (showers, baths, small draws, guests) |
| `archetypes.py` | Household archetypes and their fleet weights |
| `calendar_hr.py` | Croatian holidays incl. computed Easter, school breaks, annual leave |
| `year.py` | One archetype, one year, minute timestep |
| `estimator.py` | Interval (set-membership) observer and anchor detection |
| `experiment.py` | Harness shared by the `run_*` entry points |
| `scenarios.py` | Scenario definitions |
| `run_*.py` | Entry points that produce data or tables |
| `analyse_*.py` | Read the dataset, produce the figures quoted in `docs/05-sinteza.md` |
