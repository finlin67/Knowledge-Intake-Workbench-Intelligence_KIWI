# Developer Handoff: Wiki Over-Classification

## Purpose of this tool

Knowledge Intake Workbench ingests local files and prepares them for LLM-ready retrieval systems (AnythingLLM and Open WebUI). It should reduce manual sorting by classifying and exporting files into meaningful workspace buckets while preserving resumable state.

Primary responsibilities:

- scan and track files in a project-local SQLite DB
- classify each file into category/workspace/subfolder
- normalize and export content for downstream tools
- persist run progress to survive interruptions
- surface low-confidence files in a review queue

## Expected workspace outcomes

The system is expected to route files into:

- `career_portfolio` (portfolio-quality work)
- `archive` (general/reference/legacy content)
- `ai_projects` (project and technical artifacts)
- `case_studies` (high-value narrative outcomes)
- `wiki` (small low-context fragments only)
- `unassigned` (review queue when uncertain)

## How classification is supposed to work

Classification should follow a strict precedence:

1. `FORCE_RULES`
2. `NEGATIVE_RULES`
3. `COMPANY_MAP`
4. `PROJECT_MAP`
5. `DOC_TYPE_PATTERNS`
6. `CODE_EXT` for non-markdown extensions
7. small-file lane (`wiki/fragments`) for tiny low-signal items
8. relevance gate to hold low-signal items for review
9. fallback to unassigned review

Important behavior guarantees:

- broad single-token matches should not auto-assign workspace
- low confidence should clear auto workspace assignment
- fallback should require review
- AI output must be strict JSON and should not override strong deterministic rules

## Current production issue

Observed in real runs: approximately 900 of 1000 files routed to `wiki`.

Impact:

- portfolio/archive/ai_projects buckets are under-filled
- operator must manually reclassify at scale
- confidence in pipeline automation is reduced

## Root-cause hypothesis

The strongest likely contributor was extension bias: `.md` files were auto-classified via `CODE_EXT` to `markdown -> wiki` before relevance/fallback logic could gate uncertain cases.

This disproportionately affects corpora where most files are markdown.

## Changes applied in this branch

1. UI settings exposed:
   - `relevance_min_score`
   - `small_file_char_threshold`
2. Preflight preview includes:
   - relevance-gated count
   - small-file lane count
3. Classifier guardrail:
   - markdown extension no longer auto-routes to wiki purely by extension
   - markdown now flows through small-file/relevance/fallback unless a stronger earlier rule matched
4. Tests added for:
   - small-file lane behavior
   - relevance gate behavior
   - markdown extension not auto-routing to wiki

## What is still not ideal

- relevance scoring is still heuristic and may miss corpus-specific signals
- there is no hard "wiki share cap" safety gate before run
- run telemetry is limited (reason distribution/histograms should be richer)

## Recommended next implementation steps

1. Add classification telemetry:
   - reason family counts
   - relevance score histogram
   - char/token length histogram
2. Add a preflight safety cap:
   - block run if predicted wiki share exceeds configured threshold
3. Add calibration flow:
   - sample pending files and suggest threshold/rule adjustments
4. Expand configurable relevance phrases:
   - include customer/domain-specific terms from actual corpus

## Acceptance criteria

- wiki share is no longer dominant by default on representative corpora
- uncertain files route to review (`unassigned`) instead of generic wiki
- dry-run explains routing causes clearly
- existing rule precedence and AI safety constraints remain intact
