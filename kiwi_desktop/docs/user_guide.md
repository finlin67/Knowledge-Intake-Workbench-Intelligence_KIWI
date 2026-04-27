# KIWI User Guide — What to Click, When, and Why
This guide is written for first-time operators and non-developers. Every button name below matches the desktop UI label exactly. For installation and a five-minute quick start, see the [README](../README.md).

---

## Before you start (always)

1. Launch the app: run `kiw gui` or double-click the launcher.
2. In the header, set **Raw Folder** (your source documents) and **Output Folder** (where KIWI writes results).
3. Choose one:
   - Click **Create Project** for a brand-new output location.
   - Click **Load Project** for an existing output location that already has `.kiw/project.json`.
4. Confirm the banner no longer says "no project loaded."

**Why:** Scan and Run actions are blocked until a project is loaded. The app also validates that the header folder fields match the loaded project — if they differ, actions are blocked by design.

**Do not click yet:**
- **Scan** or **Run** before **Create Project** or **Load Project**.
- **Factory Reset** unless you intentionally want to delete `.kiw`, `exports`, and `normalized`.

---

## Scenario 1 — First-time import (simple and safe)

Use this for initial onboarding with a new dataset.

1. Keep **UI Mode = Simple Mode** enabled (the default).
2. Click **Scan Batch**.
3. Open the **Queue** tab and review the "Current Batch Queue" count.
4. Open **Run Monitor** and click **Refresh Preflight Summary**.
5. Read the summary:
   - `Pending for active profile`
   - `Pending in current raw folder`
   - `Estimated review-needed files`
6. Click **Run Batch**.
7. Watch **State**, counters, and the log panel in **Run Monitor**.
8. After completion, check your output folder and the manifest files.

**Why:**
- Preflight tells you exactly what will run before you commit time to processing.
- Reviewing the Queue prevents accidentally picking up stale items from a different raw folder.

**Do not click yet:**
- **Run Both Profiles** on your first test run — do one profile first and verify outputs before running both.
- **Clear Pending Queue** before your first successful run — you may hide work you expected to process.

---

## Scenario 2 — Daily incremental update (new files added)

Use this when you already have a project and only some source files have changed.

1. Click **Load Project**.
2. Confirm the **Raw Folder** and **Output Folder** fields match your intended project.
3. Click **Scan Batch**.
4. Open the **Queue** tab and verify new or changed files appear in "Current Batch Queue."
5. Click **Run Batch**.
6. Review **Run Monitor** for failures and review-required counts when the run completes.

**Why:**
- Scan updates the tracked inventory and queue eligibility. Running without scanning may skip newly added files.

**Do not click:**
- **Requeue All** unless you explicitly want to reprocess every tracked file, not just new ones.
- **Factory Reset** for routine updates — it permanently deletes project state and generated outputs.

---

## Scenario 3 — Generating both export layouts

Use this when downstream tools require both AnythingLLM and Open WebUI formats simultaneously.

1. Set **Active Export Profile** to `anythingllm`.
2. Click **Run Both Profiles**.
3. Let the AnythingLLM pass complete.
4. If prompted, approve the Open WebUI follow-up run.
5. Verify both export trees under `<output>/exports/`.

**Why:**
- KIWI runs AnythingLLM first, then automatically requeues the current batch for Open WebUI. This avoids the errors that come from manually switching profiles mid-batch.

**Do not click during this flow:**
- **Requeue Current Batch** mid-run — it can create confusion about what is and isn't pending.
- **Stop** unless you intentionally want to end the active loop before Open WebUI completes.

---

## Scenario 4 — Mid-run control (pause, resume, stop)

Use this when a run is in progress and you need to intervene without losing your place.

1. Click **Pause** to temporarily halt active work.
2. Click **Resume** to continue from where it stopped.
3. Click **Stop** to request full run termination.
4. After stop completes, click **Refresh Preflight Summary** to review remaining pending items.

**Why:**
- **Pause** is reversible and best for short interruptions (a few minutes).
- **Stop** ends the active run loop cleanly and is better for larger context changes — switching folders, updating settings, or changing the export profile.

**Do not do this:**
- Edit the Raw Folder or Output Folder fields and immediately click **Run** without first re-loading the project. If the fields differ from the loaded project context, the run is blocked by design.

---

## Scenario 5 — Review and manual corrections (Expert Mode)

Switch **Simple Mode** off to access the full classification audit controls.

1. Open the **Inventory** tab.
2. Filter to **Review Required** or **Failed**.
3. Select rows and use the available actions:
   - **Apply to Selected Rows** — override category or workspace in bulk
   - **Assign Workspace** — set a specific workspace for selected files
   - **Assign Subfolder** — set a subfolder within the assigned workspace
   - **Mark Review Resolved** — clear the review-required flag once you've verified the assignment
4. Open the **Review** tab for a grouped view of all flagged queues.
5. Use:
   - **Mark Approved** when the existing assignment is correct
   - **Retry Selected** for failed rows after you've addressed the root cause
6. Re-run with **Run** to process any newly unblocked files.

**Why:**
- Review-required flags are expected outcomes — they fire whenever the classifier falls back, hits a low-confidence match, or flags a broad/risky keyword. They're a quality signal, not an error.
- Manual approval and retry keep full auditability while unblocking pipeline throughput.

**Do not:**
- Click **Retry Selected** repeatedly without identifying and fixing the failure cause. Retrying a broken file will keep failing.

---

## Scenario 6 — Queue cleanup and reprocessing controls (Advanced)

Use these controls only when you understand their effect on run eligibility. They change what files will run — they do not modify source files.

| Control | When to use it |
|---|---|
| **Requeue Current Batch** | You want files in the current raw folder to run again for the active profile |
| **Requeue All** | Full reprocessing across all tracked files (all folders, all profiles) |
| **Clear Pending Queue** | You intentionally want to mark current pending items as completed for the active profile without processing them |
| **Clear Other Pending** *(Queue tab)* | You want to clear pending items that belong to a different raw folder |

**Do not use casually:**
- **Clear Pending Queue** as a substitute for fixing failed or review-required items. Clearing the queue hides the backlog — it doesn't resolve it.

---

## Scenario 7 — Factory Reset (destructive)

Use only when you want to completely restart project output state from scratch.

1. Ensure no run is active.
2. Click **Factory Reset**.
3. Read the warning dialog carefully.
4. Type `RESET` to confirm.

**What it permanently deletes** under the selected output folder:
- `.kiw/` (project metadata and database)
- `exports/` (all export profile outputs)
- `normalized/` (all normalized markdown files)

**Why you would use this:**
- Your classification rules have changed significantly and you want clean output without artifacts from previous runs.
- You're starting a completely new project in the same output folder.

**Do not use for:**
- Routine rescans — just click **Scan** and **Run**.
- Minor classification corrections — use the Review tab instead.
- Single-run cleanup — use **Clear Pending Queue** or **Requeue Current Batch**.

---

## Quick decision guide

| Button | What it does |
|---|---|
| **Create Project** | Creates new project metadata and database in the output folder |
| **Load Project** | Re-opens an existing project from the output folder |
| **Scan Batch** | Discovers and indexes files from the raw folder |
| **Run Batch** | Processes pending files for the active export profile |
| **Run Both Profiles** | Runs AnythingLLM then Open WebUI sequentially |
| **Pause** | Temporarily halts the active run |
| **Resume** | Continues a paused run |
| **Stop** | Terminates the active run loop cleanly |
| **Refresh Preflight Summary** | Updates the pre-run dashboard with current counts |
| **Requeue Current Batch** | Makes the current raw-folder batch eligible to run again |
| **Requeue All** | Makes all tracked files eligible to run again |
| **Clear Pending Queue** | Marks pending items completed for the active profile (no processing) |
| **Mark Approved** | Clears review-required for a correctly assigned file |
| **Retry Selected** | Re-queues failed files for another attempt |
| **Factory Reset** | Permanently deletes all project state and generated outputs |

---

## Understanding classification outcomes

When KIWI finishes processing a file, every file gets a `matched_by` value that tells you how the decision was made:

| `matched_by` value | What it means |
|---|---|
| `force_rule` | A FORCE_RULES entry matched the filename — highest confidence, no AI needed |
| `negative_rule` | A NEGATIVE_RULES entry blocked the file from a workspace |
| `company` | A COMPANY_MAP entry matched |
| `project` | A PROJECT_MAP entry matched |
| `pattern` | A DOC_TYPE_PATTERNS keyword matched, or the small-file lane fired |
| `ollama` / `claude` / `openai` | AI provider classified the file |
| `fallback` | Nothing matched — file is unassigned and flagged for review |

Files with `review_required = true` need your attention in the **Review** or **Triage** tab. This is normal — it's the classifier asking for a human decision rather than guessing.

---

## Tips for getting the most out of KIWI

**Start with FORCE_RULES.** Your most common project names and client names in `FORCE_RULES` will handle the bulk of your files instantly — no AI calls, no ambiguity, very fast runs.

**Use the Triage tab before running AI.** The five stat cards tell you whether your rules are working well. If "rule gaps" is high, add more FORCE_RULES or COMPANY_MAP entries before enabling AI — rules are cheaper and faster than AI for known patterns.

**Run one profile first.** On your first run with a new dataset, use AnythingLLM only. Verify the outputs look correct, then run Open WebUI. This makes it much easier to spot classification issues before they appear in both export trees.

**Check Preflight before every run.** The `preflight_wiki_share_cap` guard will block a run if too many files are predicted to land in `wiki`. This is intentional — it means your rules have gaps. Add entries and re-check before proceeding.

**Keep your API key costs in check.** With `ai_mode = ai_only_unclassified`, AI is only called for files that didn't match any rule. Pair this with good FORCE_RULES coverage and you'll make very few API calls per run.
