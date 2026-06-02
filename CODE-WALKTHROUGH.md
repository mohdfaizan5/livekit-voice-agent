# UnlockPi Agent — Code Walkthrough

A modular Python voice AI tutor built on the LiveKit Agents SDK. The agent conducts structured classroom sessions with interactive board tools, cognitive games, multi-agent handoffs, and optional database-backed team scoring.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Project Structure](#project-structure)
3. [Startup & Session Lifecycle](#startup--session-lifecycle)
4. [Session State](#session-state)
5. [Agent Personas](#agent-personas)
6. [Model Fallback Chains](#model-fallback-chains)
7. [Tools](#tools)
8. [Board System](#board-system)
9. [RPC Bridge](#rpc-bridge)
10. [Database Layer](#database-layer)
11. [Prompts](#prompts)
12. [Configuration Reference](#configuration-reference)
13. [Extension Guide](#extension-guide)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.13+ |
| Voice Framework | LiveKit Agents SDK ~1.3 |
| STT | AssemblyAI (Deepgram + Cartesia fallbacks) |
| LLM | OpenAI GPT-4.1-mini (Google Gemini 2.5 Flash fallback) |
| TTS | Inworld TTS (Cartesia Sonic-3 fallback) |
| VAD | Silero (pre-warmed) |
| Database | asyncpg (optional, Neon/Supabase PostgreSQL) |
| Session Context | Supabase Python SDK |
| Package Manager | uv |

---

## Project Structure

```
unlockpi.ai-agent/
├── agent.py                 # Slim entrypoint: server setup, session lifecycle
├── config.py                # All model names, voices, env vars centralized here
├── livekit.toml             # LiveKit Cloud project metadata
├── pyproject.toml           # Python dependencies
├── Dockerfile               # Container definition
├── agents/
│   ├── session_data.py      # Shared mutable state across tools + handoffs
│   ├── tutor_agent.py       # PiTutorAgent — main classroom persona
│   └── interview_agent.py   # InterviewAgent — mock interview persona
├── helpers/
│   ├── model_fallbacks.py   # Fallback chain builders (STT/LLM/TTS)
│   ├── board_engine.py      # Pure functional board operations
│   ├── room_utils.py        # RPC bridge + participant lookup
│   └── db.py                # Async DB pool management
├── tools/
│   ├── display_tools.py     # highlight_text, update_content
│   ├── board_tools.py       # write_to_board, update_board_line, add_board_block, etc.
│   ├── visual_tools.py      # render_visual (strict schema validation)
│   ├── game_tools.py        # start_cognitive_test
│   └── score_tools.py       # update_team_score, get_team_scores
├── board_types/
│   └── __init__.py          # TypedDict definitions mirroring frontend TypeScript types
├── prompts/
│   ├── mit-tutor.md         # Primary tutor system prompt (~800 lines)
│   ├── mit-interview.md     # Interview coach prompt (~500 lines)
│   └── bmsce-tutor.md       # Alternative BMSCE principal persona
└── tests/
    └── test_model_fallbacks.py  # Unit tests for fallback chain logic
```

---

## Startup & Session Lifecycle

### Entry Point (`agent.py`)

```python
# 1. Prewarm: load Silero VAD once per worker process
async def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# 2. Per-room session handler
@server.rtc_session
async def session(ctx: JobContext):
    ...
```

### Session Setup Sequence

```
Worker starts → prewarm() loads Silero VAD into process memory
                                  ↓
Room connection established → @rtc_session fires
                                  ↓
Create SessionData (empty state container)
                                  ↓
If session_id in room metadata → load session context from Supabase
  (title, topic, learning_goals, lesson_structure)
                                  ↓
Build model fallback chains (STT / LLM / TTS)
                                  ↓
Configure AgentSession with voice pipeline + VAD
                                  ↓
Subscribe metrics callback → logs EOUMetrics, LLMMetrics, STTMetrics, TTSMetrics
                                  ↓
Start PiTutorAgent → on_enter() fires
                                  ↓
Agent greets teacher, reads session context, begins lesson
```

### Shutdown

The DB pool is closed via a shutdown callback registered during session setup — `close_db_pool(session_data.db_pool)`.

---

## Session State

### `SessionData` (`agents/session_data.py`)

A plain dataclass attached to `AgentSession.userdata`. Shared across all tool calls and agent handoffs without needing constructor arguments or global state.

```python
@dataclass
class SessionData:
    db_pool: asyncpg.Pool | None       # Optional DB for team scores

    # Board
    board_document: BoardDocument      # Source of truth for structured board

    # Lesson context (loaded from Supabase teaching_sessions table)
    session_title: str
    session_topic: str
    session_goals: str
    session_structure: str

    # Lesson phase tracking
    lesson_phase_order: list[str]      # e.g. ["warmup", "concept", "practice", "exit"]
    current_phase_index: int
    lesson_goal_checklist: list[str]   # Parsed individual goals
    covered_goals: set[str]            # Goals marked as achieved

    # Cognitive game state
    current_answers: list[dict]        # Answers for active cognitive test
```

---

## Agent Personas

### `PiTutorAgent` (`agents/tutor_agent.py`)

The main classroom agent. Loaded with `prompts/mit-tutor.md`.

**Tools available:** `highlight_text`, `update_content`, `render_visual`, `write_to_board`, `add_board_block`, `highlight_board_line`, `clear_board_content`

**Key methods:**

`on_enter()` — Called when the agent becomes active. Parses the session goals and structure from `SessionData`, initializes lesson phase ordering, then calls `_apply_runtime_session_instructions()` to append structured lesson context to the base prompt.

`_apply_runtime_session_instructions()` — Appends the session title, topic, goal checklist, current phase, and governance rules to the live system prompt. This means the agent always knows exactly what lesson it's teaching without that context being in the static prompt file.

`mark_goal_covered(goal)` — Marks a learning goal as achieved. Updates the live instructions so the agent doesn't re-teach it.

`advance_lesson_phase(next_phase)` — Moves to the next phase in the lesson sequence and updates runtime instructions.

`transfer_to_interview()` — Returns an `InterviewAgent` instance. LiveKit swaps the active agent; `SessionData` persists.

### `InterviewAgent` (`agents/interview_agent.py`)

A narrower persona loaded with `prompts/mit-interview.md`. Presents as Dr. Kini, an interview coach.

**Tools available:** `update_content`, `render_visual`, `write_to_board`, `clear_board_content`

`on_enter()` — Greets as Dr. Kini, reminds the student of skills-first philosophy, asks if they're ready.

`transfer_to_tutor()` — Hands back to `PiTutorAgent`.

**Why separate agents?** Fewer tools + a focused prompt reduces token overhead and makes mode transitions deterministic.

---

## Model Fallback Chains

### Configuration (`config.py`)

All models are configured centrally via dataclasses with environment variable overrides:

```python
STTConfig:  model="assemblyai/universal-streaming-multilingual", language="en-IN"
LLMConfig:  model="openai/gpt-4.1-mini"
TTSConfig:  model="inworld/inworld-tts-1-max", voice="Arjun", language="en"
TurnDetectionConfig: model="english"
```

Override any value via environment variables:
```
LIVEKIT_STT_MODEL, LIVEKIT_LLM_MODEL, LIVEKIT_TTS_MODEL,
LIVEKIT_TTS_VOICE, LIVEKIT_STT_FALLBACK_MODELS (comma-separated), ...
```

### Fallback Builder (`helpers/model_fallbacks.py`)

```python
stt_fallback_descriptors(config)  → fallback STT models (language suffix inherited)
llm_model_chain(config)           → [primary, ...fallbacks] (deduped, primary first)
tts_model_chain(config)           → [primary:voice, ...fallbacks]
```

The primary model is always first in the chain. Duplicates are removed while preserving order. Language/voice suffixes are appended to fallback descriptors that are missing them.

At session start, `describe_fallback_chains()` logs a summary of all three chains.

---

## Tools

All tools are standalone `@function_tool` decorated functions, not agent methods. This allows the same tool to be shared across multiple agent classes.

### Display Tools (`tools/display_tools.py`)

**`highlight_text(context, words)`** — Sends RPC `highlight_text`. Expects a JSON array of `{"word": str, "type": "highlight|underline|secondary"}`. Used to visually emphasize key terms while speaking.

**`update_content(context, text)`** — Sends RPC `update_content` with a Markdown string. Also clears the structured board in `SessionData` to prevent stale mixed-mode state. Supports tables, formulas, checklists, code, and Mermaid blocks.

### Board Tools (`tools/board_tools.py`)

Seven tools for operating on the structured `BoardDocument`:

| Tool | RPC Sent | Description |
|---|---|---|
| `write_to_board` | `set_board` | Replace entire board with new document |
| `update_board_line` | `board_operation` (updateLine) | Change a line's text |
| `add_board_block` | `board_operation` (addBlock) | Add a new block |
| `highlight_board_line` | `board_operation` (highlightLine) | Set highlight type on a line |
| `insert_board_line` | `board_operation` (insertLineAfter) | Insert line after target |
| `delete_board_line` | `board_operation` (deleteLine) | Remove a line |
| `clear_board_content` | `clear_board` | Reset to empty board |

Each tool: reads `context.userdata.board_document` → applies operation via `board_engine.apply_operation()` → writes back → sends RPC.

### Visual Tools (`tools/visual_tools.py`)

**`render_visual(context, visual_json)`** — Validates strict schemas, then sends RPC `render_visual`.

Supported types:

| Type | Required Fields | Animation |
|---|---|---|
| `map` | locations (lat/lng), connections | route, speed |
| `chart` | labels, values, chartType (bar/line/pie) | grow, duration |
| `flow` | nodes (id/label), edges (from/to) | step, delay |
| `graph` | nodes (id/label), edges (source/target) | force, expand |

Invalid schemas are rejected before reaching the frontend.

### Game Tools (`tools/game_tools.py`)

**`start_cognitive_test(context, question, answers)`** — Sends RPC `start_cognitive_test` to trigger a Family Feud-style quiz on the classroom display. Answer JSON: `[{"text": str, "percentage": int}, ...]`. Stores answers in `SessionData.current_answers` for reveal tracking.

### Score Tools (`tools/score_tools.py`)

**`update_team_score(context, team_name, points)`** — Updates the team's score in the database and syncs all scores to the frontend via `update_scores` RPC.

**`get_team_scores(context)`** — Fetches current scores for all teams from the database.

Teams are normalized to "Team Alpha", "Team Beta", "Team Gamma".

---

## Board System

### Architecture

The Python backend is the **source of truth** for board state. The frontend is a pure view layer that receives and renders operations.

### Board Engine (`helpers/board_engine.py`)

Pure functions (no side effects) that operate on `BoardDocument`:

```python
create_empty_board() → {"id": "board-1", "version": 0, "blocks": []}

apply_operation(doc, op) → new_doc_with_bumped_version
```

Every `apply_operation` call returns a **new document** with `version` incremented. This mirrors the TypeScript board engine on the frontend for behavioral parity.

### BoardDocument Schema (`board_types/__init__.py`)

TypedDicts that mirror the frontend TypeScript types exactly:

```python
class Line(TypedDict):
    id: str
    text: str
    highlight: NotRequired[HighlightType]   # "important"|"definition"|"warning"|"exam"|"focus"|"note"

class ParagraphBlock(TypedDict):
    id: str
    type: Literal["paragraph"]
    lines: list[Line]

class FormulaBlock(TypedDict):
    id: str
    type: Literal["formula"]
    formula: str        # LaTeX

class DiagramBlock(TypedDict):
    id: str
    type: Literal["diagram"]
    diagramType: Literal["mermaid"]
    content: str

class BoardDocument(TypedDict):
    id: str
    version: int
    blocks: list[Block]
```

### `board_to_summary(doc)` (`helpers/board_engine.py`)

Generates a compact text representation of the current board injected into the agent's context. This lets the LLM know what's on the board without re-reading raw JSON.

---

## RPC Bridge

### `send_rpc` (`helpers/room_utils.py`)

```python
async def send_rpc(method: str, payload: dict, timeout: int = 10, frontend_id: str | None = None):
    identity = frontend_id or get_frontend_identity(room)
    await room.local_participant.perform_rpc(
        destination_identity=identity,
        method=method,
        payload=json.dumps(payload),
        response_timeout=timeout,
    )
```

All tools call `send_rpc` — no RPC boilerplate is duplicated across tools.

### `get_frontend_identity` (`helpers/room_utils.py`)

Participant lookup order:
1. Exact match on `"teacher-interface"` identity
2. Heuristic: participant identity contains `"teacher"` or `"frontend"`
3. Fallback: single remote participant if only one exists

### Full RPC Command Table

| Method | Sender | Receiver | Payload |
|---|---|---|---|
| `board_operation` | Agent | Frontend | `BoardOperation` dict |
| `set_board` | Agent | Frontend | `BoardDocument` dict |
| `update_content` | Agent | Frontend | `{ text: string }` |
| `highlight_text` | Agent | Frontend | `{ words: [{word, type}] }` |
| `clear_board` | Agent | Frontend | `{}` |
| `render_visual` | Agent | Frontend | `VisualPayload` dict |
| `start_cognitive_test` | Agent | Frontend | `{ question, answers }` |
| `reveal_answer` | Agent | Frontend | `{ index: int }` |
| `update_scores` | Agent | Frontend | `{ scores: Record<string, number> }` |
| `show_error_buzzer` | Agent | Frontend | `{}` |
| `update_transcript` | Agent | Frontend | `{ speaker, text }` |

---

## Database Layer

### `helpers/db.py`

```python
create_db_pool() → asyncpg.Pool | None
close_db_pool(pool) → None
```

Tries environment variables in order: `NEONDB_URL`, `DATABASE_URL`, `SUPABASE_DB_URL`. Returns `None` if none are set — DB is optional. Voice tutoring works fully without it.

The pool is created once per session and closed on shutdown. Team score tools check `db_pool is None` before executing and return a graceful message if unavailable.

---

## Prompts

All prompts are `.md` files loaded at agent instantiation. This means you can iterate on prompts without code deploys.

### `prompts/mit-tutor.md` (~800 lines)

The primary tutor persona. Key sections:
- **Identity** — UnlockPi tutor; thoughtful, storytelling, practical
- **Core beliefs** — Skills > degrees; Job Taxonomy; intrapreneurship; faculty as nation-builders
- **Tool usage rules** — When to call each tool, with schema examples
- **Visualization intent** — geography→map, numbers→chart, process→flow, relationships→graph
- **Strict output rules** — Plain speech only; Markdown only on board tools; no JSON in TTS output

### `prompts/mit-interview.md` (~500 lines)

Interview coach persona (Dr. Kini). Key sections:
- **Interview structure** — Intro, category questions, feedback scoring
- **Scoring rubric** — 9-10 exceptional, 1-2 poor
- **Transfer rule** — `transfer_to_tutor()` on any exit keyword (immediate, no farewell)

### `prompts/bmsce-tutor.md` (~700 lines)

Alternative persona — Dr. Bheemsen Arya, BMSCE Principal. Vision around engineering for Viksit Bharat 2047 and BMSCE's centenary in 2046.

### Dynamic Runtime Instructions

`PiTutorAgent._apply_runtime_session_instructions()` appends session-specific context to the base prompt at runtime:

```
[SESSION CONTEXT]
Title: {session_title}
Topic: {session_topic}
Phase: {current_phase}

GOALS CHECKLIST:
- [ ] Goal 1
- [x] Goal 2  ← marked when covered

LESSON STRUCTURE:
{session_structure}
```

This keeps the static prompt file clean and reusable across any lesson topic.

---

## Configuration Reference

### Environment Variables

```
# LiveKit (required)
LIVEKIT_URL                     WebSocket URL of LiveKit server
LIVEKIT_API_KEY                 LiveKit API key
LIVEKIT_API_SECRET              LiveKit API secret

# Model overrides (all optional — defaults in config.py)
LIVEKIT_STT_MODEL               Primary STT model descriptor
LIVEKIT_STT_LANGUAGE            STT language code (default: en-IN)
LIVEKIT_STT_FALLBACK_MODELS     Comma-separated fallback STT models
LIVEKIT_LLM_MODEL               Primary LLM model descriptor
LIVEKIT_LLM_FALLBACK_MODELS     Comma-separated fallback LLM models
LIVEKIT_TTS_MODEL               Primary TTS model descriptor
LIVEKIT_TTS_VOICE               TTS voice name (default: Arjun)
LIVEKIT_TTS_LANGUAGE            TTS language (default: en)
LIVEKIT_TTS_FALLBACK_MODELS     Comma-separated fallback TTS models
LIVEKIT_TURN_DETECTION_MODEL    english | multilingual (default: english)

# Supabase (for session context loading)
SUPABASE_URL                    Supabase project URL
SUPABASE_SERVICE_ROLE_KEY       Service role key

# Database (optional — for team scores)
NEONDB_URL                      PostgreSQL connection URL (Neon)
DATABASE_URL                    PostgreSQL connection URL (generic)
SUPABASE_DB_URL                 PostgreSQL connection URL (Supabase direct)
```

### `livekit.toml`

```toml
[project]
  subdomain = "unlockpi-xqgpomfl"

[agent]
  id = "CA_rMKEpZKoWdDv"
```

---

## Extension Guide

### Adding a New Tool

1. Create `tools/<name>.py` with `@function_tool` decorated function
2. Import `context.userdata` as `SessionData` for shared state
3. Call `send_rpc(method, payload)` from `helpers.room_utils` to update the frontend
4. Add the function to the agent's `tools=[...]` list in `tutor_agent.py` or `interview_agent.py`
5. Add a corresponding RPC handler on the frontend

### Adding a New Agent Persona

1. Create `agents/<mode>_agent.py` inheriting from `Agent`
2. Add `prompts/<mode>.md` system prompt
3. Define handoff tools in both directions (e.g., `transfer_to_tutor`, `transfer_to_<mode>`)
4. Keep cross-mode state in `SessionData`
5. Lazy-import the other agent class to avoid circular imports

### Adding a New Board Operation

1. Add handler in `helpers/board_engine.py` inside `apply_operation()`
2. Add a TypedDict for the operation in `board_types/__init__.py`
3. Add a tool wrapper in `tools/board_tools.py`
4. Add the corresponding handler in the frontend's `use-classroom-realtime.ts`
5. Add the operation type to `board.ts` on the frontend

### Changing the Lesson Persona

Swap `mit-tutor.md` for a different prompt file in `PiTutorAgent.__init__()`. The dynamic session instructions injected by `_apply_runtime_session_instructions()` work with any base prompt.

### Running Tests

```bash
uv run pytest tests/test_model_fallbacks.py
```

Tests cover: STT fallback language suffix inheritance, LLM chain ordering, STT primary exclusion from fallbacks, TTS voice descriptor preservation, `describe_fallback_chains()` output shape.
