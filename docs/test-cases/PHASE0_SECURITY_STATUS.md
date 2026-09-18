# Phase 0 security test status (TDD red)

> Recorded against **current main** product code (`backend_v2.py` / `index.html`) on branch `cursor/phase0-security-tdd-red-1edf`.  
> Command: `python -m pytest tests/ -m phase0 -v`  
> Date: 2026-09-18  
> Collection: **91 tests collected** (`pytest tests/ --collect-only`); Phase 0 marker run: **27 failed, 5 passed**.  
> Existing non-Phase-0 tests: **47 passed, 12 skipped** (`tests/test_frontend.py` skipped — Windows Playwright path, `TDD_PROCESS.md` §6).

## Locked choices

| Topic | Choice in this PR |
|-------|-------------------|
| Default admin | **No seeded usable `admin`/`admin123` on a fresh DB.** `P0-TC-ADM-01` asserts `admins` has no `username=admin` **and** login with those creds fails (401/403/404). |
| Legacy parent SHA-256 | **Login succeeds and rehashes** to bcrypt/argon2 (`P0-TC-PWD-03`). Not “reject and force reset”. |
| IDOR status | **403** (not 404). |
| XSS frontend | **Manual / E2E (B).** No `escape_html` helper in `backend_v2.py`. Backend JSON round-trip is automated and currently **passes**. |

Synthetic fixture users only: `test-admin` / `TestAdmin!pass1`, `test_parent_*` / `TestParent!pass1`, kid PIN `1357`. Production `kids_town.db` is never copied.

## Mapping

| Case ID | Pytest node id | Result | Notes |
|---------|----------------|--------|-------|
| P0-TC-SESS-01 | `tests/test_authz_session.py::test_unauthenticated_post_points_returns_401` | **FAIL** | Unauth `POST .../points` is 200 today |
| P0-TC-SESS-02 | `tests/test_authz_session.py::test_unauthenticated_complete_task_returns_401` | **FAIL** | Unauth complete-task is 200 |
| P0-TC-SESS-03 | `tests/test_authz_session.py::test_unauthenticated_create_kid_returns_401` | **FAIL** | Unauth create-kid is 201 if `parent_id` in body |
| P0-TC-SESS-04 | `tests/test_authz_session.py::test_health_allows_anonymous_without_pii` | **PASS** | `GET /api/health` already anonymous 200 without PII |
| P0-TC-IDOR-01 | `tests/test_authz_idor.py::test_kid_cannot_add_points_to_other_kid_returns_403` | **FAIL** | No session; write APIs are open |
| P0-TC-IDOR-02 | `tests/test_authz_idor.py::test_kid_cannot_adjust_sibling_points_returns_403` | **FAIL** | Same |
| P0-TC-IDOR-03 | `tests/test_authz_idor.py::test_parent_cannot_forge_parent_id_on_create_kid` | **FAIL** | Body `parent_id` trusted |
| P0-TC-IDOR-04 | `tests/test_authz_idor.py::test_kid_cannot_complete_other_kids_task_returns_403` | **FAIL** | Same |
| P0-TC-IDOR-05 | `tests/test_authz_idor.py::test_parent_cannot_adjust_unlinked_kid_points_returns_403` | **FAIL** | Same |
| P0-TC-ADM-01 | `tests/test_admin_bootstrap.py::test_fresh_db_has_no_default_admin_admin123` | **FAIL** | `migrate_db_v3` inserts `admin` + sha256(`admin123`); login succeeds |
| P0-TC-ADM-02 | `tests/test_admin_bootstrap.py::test_legacy_default_admin_must_change_password_has_no_write` | **FAIL** | Login grants admin JSON; `DELETE /api/kids/<id>` is unauthenticated 200 |
| P0-TC-ADM-03 | `tests/test_admin_bootstrap.py::test_login_forms_do_not_prefill_admin123` | **FAIL** | `showAdminLogin` prefills `admin123`; backend prints `Default admin:` |
| P0-TC-PIN-01 | `tests/test_pin_hash.py::test_create_kid_stores_hashed_pin_not_plaintext` | **FAIL** | `kid_auth.pin` stored as plaintext |
| P0-TC-PIN-02 | `tests/test_pin_hash.py::test_login_response_does_not_echo_pin` | **PASS** | Unified login JSON has no `pin` when `kid_auth` exists. Legacy `/api/login` still inserts plaintext `0000` when the row is missing — covered by PIN-03 |
| P0-TC-PIN-03 | `tests/test_pin_hash.py::test_missing_kid_auth_does_not_insert_plaintext_0000` | **FAIL** | Legacy `/api/login` inserts plaintext `0000` |
| P0-TC-STAT-01 | `tests/test_static_denylist.py::test_static_route_does_not_serve_db_files` | **FAIL** | `/kids/*.db` served when the file exists |
| P0-TC-STAT-02 | `tests/test_static_denylist.py::test_static_route_does_not_serve_python_source` | **FAIL** | `/kids/backend_v2.py` served |
| P0-TC-STAT-03 | `tests/test_static_denylist.py::test_static_path_traversal_and_double_extension_denied` | **FAIL** | Disguised `secret.db.png` (sqlite header) served as image |
| P0-TC-STAT-04 | `tests/test_static_denylist.py::test_legitimate_static_assets_still_served` | **PASS** | `/kids/` and `/assets-c/house.png` already 200 |
| P0-TC-PWD-01 | `tests/test_parent_password.py::test_parent_register_password_is_salted_not_sha256` | **FAIL** | `hash_password` is unsalted SHA-256 |
| P0-TC-PWD-02 | `tests/test_parent_password.py::test_parent_password_min_length_8_and_not_returned` | **FAIL** | Min length is 4; `abcd` accepted |
| P0-TC-PWD-03 | `tests/test_parent_password.py::test_legacy_sha256_parent_rehashes_or_is_rejected` | **FAIL** | SHA-256 login succeeds and does not rehash |
| P0-TC-INV-01 | `tests/test_inventory_authz.py::test_unauthenticated_inventory_add_returns_401` | **FAIL** | Open add |
| P0-TC-INV-02 | `tests/test_inventory_authz.py::test_kid_cannot_self_grant_inventory_returns_403` | **FAIL** | Kid (or anyone) can add |
| P0-TC-INV-03 | `tests/test_authz_idor.py::test_kid_cannot_add_inventory_to_other_kid_returns_403` | **FAIL** | Cross-kid add open |
| P0-TC-PTS-01 | `tests/test_points_floor.py::test_points_cannot_go_negative_without_auth_and_floor_at_zero` | **FAIL** | Unauth `POST .../points` allows negative balance |
| P0-TC-PTS-02 | `tests/test_points_floor.py::test_add_points_parent_negative_floors_at_zero` | **FAIL** | `POST .../points` does not floor; `points/adjust` already floors at 0 |
| P0-TC-LIST-01 | `tests/test_list_kids_privacy.py::test_get_api_kids_is_not_a_public_full_list` | **FAIL** | `GET /api/kids` is a public full list |
| P0-TC-LIST-02 | `tests/test_list_kids_privacy.py::test_parent_kids_ignores_forged_parent_id_query` | **FAIL** | Query `parent_id` is trusted |
| P0-TC-XSS-01 | `tests/test_xss_encoding.py::test_task_title_roundtrip_and_escape_helper_if_present` | **PASS** (API) | JSON stores the raw title string. **Frontend DOM encoding is MANUAL** (no Playwright path on this runner; no `escape_html` helper) |
| P0-TC-XSS-02 | `tests/test_xss_encoding.py::test_kid_display_name_api_roundtrip` | **PASS** (API) | Name round-trips. **HUD `innerHTML` / onerror is MANUAL** |
| P0-TC-DEV-01 | `tests/test_authz_session.py::test_dev_dashboard_denied_for_non_admin` | **FAIL** | `GET /api/dev-dashboard` is public and includes `kid_details` |

## Accidentally passing (still valid assertions)

These five are **not** false greens of the security program; they already match desired behavior or only cover the API half:

1. **SESS-04** — health stays public. Keep.
2. **PIN-02** — successful kid login JSON does not echo PIN (legacy missing-row leak is PIN-03).
3. **STAT-04** — HTML/png still load. Keep as a regression guard when denylisting static files.
4. **XSS-01 / XSS-02** — backend round-trip only. DOM checks remain on the Phase 0 **manual (B)** list.

## Next (GREEN, not this PR)

Implement session gate, IDOR 403, stop seeding `admin/admin123`, hash PINs and parent passwords, denylist `.db`/`.py`, floor points, lock down `/api/kids` and `/api/dev-dashboard`. Do not mix Phase 1 gameplay into that follow-up.
