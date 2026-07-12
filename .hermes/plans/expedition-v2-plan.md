# Loop Engineering — 探險系統 v2 Phase 1

## Goal

```yaml
title: "[Kids-Town] P1 探險系統 v2 — Phase 1：三種探險類型基礎架構"

done_when:
  - Backend: expedition_type field added to expeditions table
  - Backend: API supports type-based expedition (explore/quiz/battle)
  - Backend: Existing timer-based exploration refactored into new type system
  - Frontend: Expedition tab shows type selector (3 types)
  - Frontend: Exploration mode works (existing refactored)
  - Frontend: Quiz mode basic UI + backend (MCQ questions from hardcoded pool)
  - Frontend: Battle mode basic UI placeholder
  - E2E: 24/24 pass
  - E2E: No new console errors
  - E2E: Assets all 200

boundaries:
  - Max 5 loops
  - 唔改 database schema 唔問
  - 唔刪 existing test
  - 唔改 login/auth flow

terminate:
  - ✅ All done → report + move card
  - ❌ Max loops → report + ask
  - ⛔ Boundary hit → ask
```
