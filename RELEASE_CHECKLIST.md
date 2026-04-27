# KIWI V1 Release Checklist (Windows Local-First)

## Packaging preflight

- [ ] Fresh clone works on a clean Windows machine
- [ ] No private paths remain in docs
- [ ] No secrets/API keys/tokens committed
- [ ] Parent README is current
- [ ] QUICK_START_WINDOWS is current
- [ ] USER_GUIDE and BEGINNER_WALKTHROUGHS are current
- [ ] README screenshots are updated
- [ ] Issue templates exist in .github/ISSUE_TEMPLATE

## Startup and shutdown

- [ ] start_kiwi.bat starts backend and web services
- [ ] Browser URL is shown clearly in startup output
- [ ] Home/Setup shows Backend: Online
- [ ] stop_kiwi.bat stops KIWI services cleanly

## Core workflow smoke test

- [ ] Save Project works
- [ ] Scan Batch works (non-zero files on sample input)
- [ ] Run Batch works
- [ ] Start Next Batch works
- [ ] Settings page opens
- [ ] AI settings review panel appears in Step 3 - Run Batch

## Repo structure and docs

- [ ] Parent repo structure matches README explanations
- [ ] KIWI_Web described as primary web UI
- [ ] kiwi_desktop described as local tooling/backend support
- [ ] Launch scripts described from parent root context
- [ ] Documentation map is present and accurate

## Optional provider checks

- [ ] Ollama path documented (optional)
- [ ] Rules-only path documented (no AI required)

## Release handoff

- [ ] Maintainer can follow RELEASE_WINDOWS_GUIDE end-to-end
- [ ] Known limitations and roadmap are up to date
