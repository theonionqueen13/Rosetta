# Rosetta

Astrological chart calculation, interpretation, and interactive exploration engine — built with [NiceGUI](https://nicegui.io/).

Rosetta computes natal, transit, and synastry charts using the Swiss Ephemeris, detects aspect patterns and circuits, renders publication-quality chart wheels, and provides an AI-assisted chat interface for guided astrological readings.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| pip | latest |
| Swiss Ephemeris data | bundled in `ephe/` |

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/theonionqueen13/Rosetta.git
cd Rosetta

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables (see below)
cp .env.example .env   # then edit .env with your keys

# 5. Run the application
python app.py
```

The app starts on **http://localhost:8080** by default.

## Environment Variables

Create a `.env` file in the project root (or set these in your deployment environment):

| Variable | Required | Description |
|---|---|---|
| `NICEGUI_STORAGE_SECRET` | **Yes** | Secret key for NiceGUI encrypted browser storage. Must be set — the app will fail fast if missing. |
| `SUPABASE_URL` | **Yes** | Supabase project URL |
| `SUPABASE_KEY` | **Yes** | Supabase anonymous/public API key (also accepts `SUPABASE_ANON_KEY`) |
| `OPENCAGE_API_KEY` | Yes | OpenCage geocoding API key (for birth-place lookups) |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key (for AI chat readings) |
| `AUTH_REDIRECT_URL` | No | OAuth redirect URL (defaults to app origin) |
| `DATABASE_URL` | No | Direct PostgreSQL connection string (for admin/migration scripts) |
| `PORT` | No | HTTP port (default: `8080`) |

## Architecture

```
app.py                   ← NiceGUI entry point (~100 lines): routes, auth guard, page assembly
config.py                ← Framework-agnostic secret / env-var reader

src/
├── core/                ← Pure computation — no UI, no DB
│   ├── calc_v2.py           Swiss Ephemeris chart calculation engine
│   ├── chart_models.py      Pydantic-style data models for chart data
│   ├── circuit_sim.py       Circuit power simulation
│   ├── data_helpers.py      DataFrame / position extraction utilities
│   ├── dignity_calc.py      Planetary strength (essential dignities)
│   ├── event_lookup_v2.py   Ingress / station event search
│   ├── geocoding.py         Place → lat/lon/tz resolution
│   ├── models_v2.py         Rich chart wrapper with aspect/pattern access
│   ├── patterns_v2.py       Aspect-pattern detection (T-squares, grand trines, etc.)
│   ├── planet_profiles.py   Per-planet interpretive profile generation
│   ├── static_data.py       Shared constants (signs, bodies, shape counts)
│   └── switch_points.py     Sign/house boundary detection
│
├── db/                  ← Database layer (Supabase + psycopg2)
│   ├── db_access.py         Direct PostgreSQL queries
│   ├── profile_helpers.py   Profile apply / convert helpers
│   ├── supabase_admin.py    Admin-check queries
│   ├── supabase_client.py   Supabase client singleton + auth wrappers
│   └── supabase_profiles.py Profile CRUD operations
│
├── rendering/           ← Chart drawing & text generation
│   ├── chart_serializer.py  Chart → D3-compatible JSON
│   ├── dispositor_graph.py  Rulership / dispositor tree layout
│   ├── drawing_primitives.py Geometry, color, and glyph helpers
│   ├── drawing_v2.py        Matplotlib chart-wheel renderer
│   ├── interp_base_natal.py Natal interpretation text engine
│   └── profiles_v2.py       Profile-text rendering & clustering
│
├── mcp/                 ← AI chat / reading pipeline
│   ├── agent_memory.py      Conversational memory management
│   ├── chat_pipeline.py     Main chat orchestration (pure logic)
│   ├── circuit_query.py     Circuit-aware query handler
│   ├── comprehension.py     Question comprehension engine
│   ├── comprehension_models.py  Parsed-question data models
│   ├── grammar_parse.py     Astrological grammar parser
│   ├── prompt_templates.py  LLM prompt construction
│   ├── prose_synthesizer.py Natural-language answer synthesis
│   ├── reading_engine.py    Full-reading orchestrator
│   ├── reading_packet.py    Reading data containers
│   ├── server.py            MCP server entry point
│   ├── term_registry.py     Astrological term normalization
│   ├── tools.py             MCP tool definitions
│   └── topic_maps.py        Topic / subtopic taxonomy
│
├── ui/                  ← NiceGUI page components
│   ├── page_state.py        PageState dataclass (shared widget refs)
│   ├── auth.py              Login / signup / session management
│   ├── layout.py            Header, drawer, tab shell
│   ├── calculate.py         Birth-data → chart calculation handler
│   ├── chart_display.py     Chart rendering & display helpers
│   ├── feedback.py          Bug-report FAB + dialog
│   ├── startup.py           Auto-load & empty-state setup
│   ├── tab_admin.py         Admin feedback reports
│   ├── tab_chart_manager.py Birth form, profile CRUD, donate
│   ├── tab_chat.py          AI chat interface
│   ├── tab_circuits.py      Circuit visualization & toggles
│   ├── tab_rulers.py        Dispositor graph & legend
│   ├── tab_settings.py      Display options, house system, mode map
│   ├── tab_specs.py         Data tables
│   ├── tab_standard.py      Aspect toggles, harmonics, synastry
│   ├── transit_controls.py  Transit compute / navigation / swap
│   └── wizard.py            Guided-topics wizard dialog
│
├── interactive_chart/   ← Client-side D3 chart (JS/CSS/HTML)
│   ├── chart_renderer.js
│   ├── d3.v7.min.js
│   ├── nicegui_index.html
│   ├── styles.css
│   └── tooltip.js
│
├── chart_adapter.py     ← Framework-agnostic chart computation adapter
├── chart_utils.py       ← Visible-object resolution logic
├── mode_map_core.py     ← Mode-map data & HTML builder
└── nicegui_state.py     ← Per-user session state management
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_calc_v2.py -v

# Run only fast tests (skip slow/integration)
pytest tests/ -v -m "not slow and not integration"
```

Test configuration is in [pyproject.toml](pyproject.toml). Coverage targets the `src/` package.

## Deployment

Rosetta is deployed via **Docker** on **Railway**.

### Docker

```bash
docker build -t rosetta .
docker run -p 8080:8080 \
  -e NICEGUI_STORAGE_SECRET=your-secret \
  -e SUPABASE_URL=https://your-project.supabase.co \
  -e SUPABASE_KEY=your-anon-key \
  -e OPENCAGE_API_KEY=your-key \
  -e OPENROUTER_API_KEY=your-key \
  rosetta
```

The [Dockerfile](Dockerfile) uses a multi-stage build: a `builder` stage compiles C extensions (pyswisseph), and the slim runtime stage copies only installed packages.

### Railway

Railway configuration is in [railway.toml](railway.toml). The `/health` endpoint returns `{"status": "ok"}` for container health checks.

### Swiss Ephemeris Data

The `ephe/` directory contains Swiss Ephemeris data files required at runtime. The `SE_EPHE_PATH` environment variable is set to `/app/ephe` in the Docker image. These files must be present for chart calculations to work.

## Project Status

See the [development plan](docs/) for the full roadmap and current progress.

## License

All rights reserved.
