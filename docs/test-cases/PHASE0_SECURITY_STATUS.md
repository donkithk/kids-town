# Phase 0 security test status (TDD green)

> Recorded against **this PR** product code (`backend_v2.py` / `index.html`) on branch `cursor/phase0-security-impl-8913`.  
> Command: `python -m pytest tests/ -m phase0 -v`  
> Date: 2026-09-18  
> Collection: **91 tests collected** (`pytest tests/ --collect-only`); Phase 0 marker run: **32 passed**.  
> Full suite: **79 passed, 12 skipped** (`tests/test_frontend.py` skipped — Windows Playwright path, `TDD_PROCESS.md` §6).

## Locked choices

| Topic | Choice in this PR |
|-------|-------------------|
| Default admin | **No seeded usable `admin`/`admin123` on a fresh DB.** Login with those creds is always 403. Optional bootstrap via `KIDS_TOWN_BOOTSTRAP_ADMIN_PASSWORD` (weak/default values refused). |
| Legacy parent SHA-256 | **Login succeeds and rehashes** to bcrypt (`P0-TC-PWD-03`). |
| IDOR status | **403** (not 404). Unauthenticated writes/sensitive reads: **401**. |
| XSS frontend | **Manual / E2E (B).** Backend JSON round-trip is automated and **passes**. |

Synthetic fixture users only: `test-admin` / `TestAdmin!pass1`, `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| P0-TC-SESS-01 | `tests/test_authz_session.py::test_unauthenticated_post_points_returns_401` | **PASS** | Flask session required on write APIs |
| P0-TC-SESS-02 | `tests/test_authz_session.py::test_unauthenticated_complete_task_returns_401` | **PASS** | |
| P0-TC-SESS-03 | `tests/test_authz_session.py::test_unauthenticated_create_kid_returns_401` | **PASS** | Body `parent_id` ignored without session |
| P0-TC-SESS-04 | `tests/test_authz_session.py::test_health_allows_anonymous_without_pii` | **PASS** | Health stays public |
| P0-TC-IDOR-01 | `tests/test_authz_idor.py::test_kid_cannot_add_points_to_other_kid_returns_403` | **PASS** | Kid cannot POST points (self or other) |
| P0-TC-IDOR-02 | `tests/test_authz_idor.py::test_kid_cannot_adjust_sibling_points_returns_403` | **PASS** | |
| P0-TC-IDOR-03 | `tests/test_authz_idor.py::test_parent_cannot_forge_parent_id_on_create_kid` | **PASS** | Session `parent_id` wins; forged body → 403 |
| P0-TC-IDOR-04 | `tests/test_authz_idor.py::test_kid_cannot_complete_other_kids_task_returns_403` | **PASS** | |
| P0-TC-IDOR-05 | `tests/test_authz_idor.py::test_parent_cannot_adjust_unlinked_kid_points_returns_403` | **PASS** | |
| P0-TC-ADM-01 | `tests/test_admin_bootstrap.py::test_fresh_db_has_no_default_admin_admin123` | **PASS** | `migrate_db_v3` no longer seeds `admin` |
| P0-TC-ADM-02 | `tests/test_admin_bootstrap.py::test_legacy_default_admin_must_change_password_has_no_write` | **PASS** | `admin`+legacy default password login is 403; DELETE still 401 |
| P0-TC-ADM-03 | `tests/test_admin_bootstrap.py::test_login_forms_do_not_prefill_admin123` | **PASS** | Prefill removed; startup banner no longer prints default creds |
| P0-TC-PIN-01 | `tests/test_pin_hash.py::test_create_kid_stores_hashed_pin_not_plaintext` | **PASS** | bcrypt `$2b$` |
| P0-TC-PIN-02 | `tests/test_pin_hash.py::test_login_response_does_not_echo_pin` | **PASS** | |
| P0-TC-PIN-03 | `tests/test_pin_hash.py::test_missing_kid_auth_does_not_insert_plaintext_0000` | **PASS** | Missing row → 403; no insert |
| P0-TC-STAT-01 | `tests/test_static_denylist.py::test_static_route_does_not_serve_db_files` | **PASS** | |
| P0-TC-STAT-02 | `tests/test_static_denylist.py::test_static_route_does_not_serve_python_source` | **PASS** | |
| P0-TC-STAT-03 | `tests/test_static_denylist.py::test_static_path_traversal_and_double_extension_denied` | **PASS** | `.db` in name / sqlite header / `..` → 404 |
| P0-TC-STAT-04 | `tests/test_static_denylist.py::test_legitimate_static_assets_still_served` | **PASS** | |
| P0-TC-PWD-01 | `tests/test_parent_password.py::test_parent_register_password_is_salted_not_sha256` | **PASS** | bcrypt, not unsalted SHA-256 |
| P0-TC-PWD-02 | `tests/test_parent_password.py::test_parent_password_min_length_8_and_not_returned` | **PASS** | |
| P0-TC-PWD-03 | `tests/test_parent_password.py::test_legacy_sha256_parent_rehashes_or_is_rejected` | **PASS** | Successful login rehashes to bcrypt |
| P0-TC-INV-01 | `tests/test_inventory_authz.py::test_unauthenticated_inventory_add_returns_401` | **PASS** | |
| P0-TC-INV-02 | `tests/test_inventory_authz.py::test_kid_cannot_self_grant_inventory_returns_403` | **PASS** | Kids and parents cannot `inventory/add`; admin-only debug |
| P0-TC-INV-03 | `tests/test_authz_idor.py::test_kid_cannot_add_inventory_to_other_kid_returns_403` | **PASS** | |
| P0-TC-PTS-01 | `tests/test_points_floor.py::test_points_cannot_go_negative_without_auth_and_floor_at_zero` | **PASS** | |
| P0-TC-PTS-02 | `tests/test_points_floor.py::test_add_points_parent_negative_floors_at_zero` | **PASS** | `POST .../points` floors at 0 |
| P0-TC-LIST-01 | `tests/test_list_kids_privacy.py::test_get_api_kids_is_not_a_public_full_list` | **PASS** | Kid sees self; parent sees linked |
| P0-TC-LIST-02 | `tests/test_list_kids_privacy.py::test_parent_kids_ignores_forged_parent_id_query` | **PASS** | Query `parent_id` ignored |
| P0-TC-XSS-01 | `tests/test_xss_encoding.py::test_task_title_roundtrip_and_escape_helper_if_present` | **PASS** (API) | **Frontend DOM encoding is MANUAL** |
| P0-TC-XSS-02 | `tests/test_xss_encoding.py::test_kid_display_name_api_roundtrip` | **PASS** (API) | **HUD `innerHTML` / onerror is MANUAL** |
| P0-TC-DEV-01 | `tests/test_authz_session.py::test_dev_dashboard_denied_for_non_admin` | **PASS** | Admin session only |

## Accidentally passing guards (still green)

1. **SESS-04** — health stays public.
2. **PIN-02** — successful kid login JSON does not echo PIN.
3. **STAT-04** — HTML/png still load after denylist.
4. **XSS-01 / XSS-02** — backend round-trip only. DOM checks remain on the Phase 0 **manual (B)** list.

## Intentional behavior decisions

- Flask **cookie session** after `/api/auth/login` and legacy `/api/login` (test client keeps `Set-Cookie`).
- Kid may not grant points or inventory even to themselves; parents may adjust/add points for **linked** kids only; `inventory/add` is **admin-only**.
- Historical default admin username+password is rejected even if a leftover row exists (no write session).
- Gameplay write routes (battle/boss/expedition) also require a session so unauthenticated clients cannot mutate kid state. Existing battle/boss HTTP tests log in as the synthetic battle kid.
