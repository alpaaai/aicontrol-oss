# Operating AIControl (self-hosted)

This guide covers running AIControl in your own environment: topology, network
and TLS, configuration, upgrades, backups, and monitoring. For first install,
see the Quick Start in [README.md](README.md).

## Topology

| Component | Container | Port | Notes |
|-----------|-----------|------|-------|
| API | `aicontrol-api` | 8001 | FastAPI. Policy engine (Cedar) runs in this process. |
| Dashboard | `aicontrol-frontend` | 3000 | nginx serving the React build. |
| PostgreSQL 15 | `postgres:15` | 127.0.0.1:5432 | Bound to the host loopback only. |

Run **one** API container with **one** uvicorn process. Three things are
per-process by design: the login/setup rate limiter (in memory), the audit
write-ahead log (a file on the `wal_data` volume), and the background jobs
(retention purge, license sync, drift detection). Running two API containers
against the same database would split the rate-limit counters, double the
background jobs, and have two migrators race on start.

## Network and TLS

AIControl does not terminate TLS. Put a reverse proxy or load balancer in front
of both ports and serve them over HTTPS.

Three settings must agree with the addresses people actually use. They default
to `localhost` and must be changed for any other hostname:

| Setting | Meaning | Where used |
|---------|---------|------------|
| `AICONTROL_API_URL` | API address **as the browser sees it** | Read by the dashboard container at start, written to `/config.js`. No image rebuild needed. |
| `FRONTEND_BASE_URL` | Dashboard address | Builds the invite links admins send to new users. |
| `CORS_ORIGINS` | Comma-separated dashboard origins the API accepts | API CORS policy. |

Example, dashboard at `https://aicontrol.example.com` and API at
`https://aicontrol-api.example.com`:

```
AICONTROL_API_URL=https://aicontrol-api.example.com
FRONTEND_BASE_URL=https://aicontrol.example.com
CORS_ORIGINS=https://aicontrol.example.com
```

Same-origin alternative: the dashboard container proxies `/api/` to the API
container. Publish only port 3000 through your proxy and set
`AICONTROL_API_URL=/api`. The browser then makes no cross-origin calls and
`CORS_ORIGINS` is not involved. Agents and Slack still need to reach the API
itself (port 8001, or your own route to it).

After changing `.env`: `docker compose -f docker-compose.yml -f docker-compose.app.yml up -d`.

### Client IP behind a proxy

Login and setup attempts are rate limited per client IP. uvicorn only trusts
`X-Forwarded-For` from addresses in `FORWARDED_ALLOW_IPS` (default
`127.0.0.1`). Behind a proxy, every user otherwise appears to come from the
proxy's address and shares one rate-limit bucket. Set `FORWARDED_ALLOW_IPS` to
your proxy's address (or the container network's range) in `.env`. Only do
this when the API port is reachable solely through that proxy.

### Outbound connections

| Destination | When | Needed for |
|-------------|------|------------|
| `slack.com` API | Business/Enterprise with `SLACK_BOT_TOKEN` set | Review notifications |
| Your LLM provider | When `LLM_MOCK_ENABLED=false` | AI-native features, with your own key |
| Registered downstream MCP servers | Every governed tool call | The gateway forwards allowed calls |
| `fonts.googleapis.com` (from users' **browsers**) | Dashboard load | Typefaces. Blocked: the dashboard renders with system fonts. |

A Community install with mock LLM needs no outbound access from the servers.

Inbound: Slack must reach `POST /slack/actions` on the API for the approve/deny
buttons. Set `SLACK_SIGNING_SECRET`; requests are rejected without it.

## Configuration reference

All settings are environment variables, normally in `.env` next to the compose
files (`install.sh` creates it, mode 600).

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | required | `postgresql+asyncpg://user:pass@host:5432/db`. URL-encode special characters in the password. |
| `SECRET_KEY` | `changeme` | Signs every JWT. With `APP_ENV=production` the API refuses to start on the default. Use 32+ random characters. |
| `APP_ENV` | `development` | `production` switches logs to JSON and enables the secret check. |
| `CORS_ORIGINS` | `http://localhost:3000` | See above. |
| `FRONTEND_BASE_URL` | `http://localhost:3000` | See above. |
| `AICONTROL_API_URL` | build default | See above (dashboard container). |
| `WAL_DIR` | `/app/data/wal` in compose | Audit WAL location (`wal_data` volume). |
| `REPORTS_DIR` | `/app/reports` in compose | Compliance report output (`reports_data` volume). |
| `RETENTION_PURGE_INTERVAL_HOURS` | `24` | How often expired audit events are deleted. |
| `DRIFT_SCAN_INTERVAL_HOURS` | `6` | Enterprise drift scan interval. |
| `DRIFT_UNSEEN_TOOL_LOOKBACK_DAYS` | `30` | Drift scan lookback. |
| `REVIEW_TIMEOUT_MINUTES` | `60` | Sets each review's response deadline. The dashboard counts reviews past it as overdue; pending reviews are not auto-resolved. |
| `HITL_RETRY_WINDOW_MINUTES` | `15` | After a review is approved, an identical retried call in the same session is allowed for this long. |
| `MCP_RESPONSE_SCAN_POLICY` | `block` | `block` rejects a tool response flagged unsafe; `log` records it only. |
| `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_REVIEW_CHANNEL` | unset / `#aicontrol-reviews` | Slack review notifications (Business+). |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_MOCK_ENABLED` | anthropic / haiku / empty / `false` | AI-native features on your own account. |
| `DEMO_MODE` | `false` | Exposes unauthenticated demo endpoints that delete audit rows. Never enable on a real install. |

Compose-level variables (read by `docker-compose.app.yml`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `AICONTROL_VERSION` | `latest` | Image tag for both the API and dashboard images. |
| `RUN_MIGRATIONS` | `true` | Apply pending migrations when the API container starts. |

`python3 scripts/public/check_env_completeness.py .env` lists settings added in newer
releases that your `.env` does not mention yet.

## Install, upgrade, rollback

Install: `bash install.sh`, then `bash verify.sh`.

Upgrade:

```bash
# 1. Back up first (see below).
# 2. Pull and restart. Migrations run automatically on API start.
docker compose -f docker-compose.yml -f docker-compose.app.yml pull
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d
bash verify.sh
```

Pin a version instead of following `latest` by setting `AICONTROL_VERSION` in
`.env` to a release tag or a build date (for example `2026-10-20`). The API
refuses to start if a migration fails.

Rollback: migrations are not reversed automatically. To go back, set
`AICONTROL_VERSION` to the previous tag **and restore the database backup taken
before the upgrade**.

If you manage migrations yourself, set `RUN_MIGRATIONS=false` and run
`docker compose -f docker-compose.yml -f docker-compose.app.yml exec api alembic upgrade head`.

Seed policies (`block_dangerous_tools` and the other shipped defaults and library
templates) are re-applied from the release at every API start. The one setting
that is preserved is `active`: a policy you switch on or off stays that way.
Edits to a seed policy's conditions are overwritten; create a new policy with
a different name to customize.

## Backup and restore

State lives in the Postgres volume (`pgdata`), the audit WAL volume
(`wal_data`), and the compliance report volume (`reports_data`).

```bash
# Database dump
docker compose -f docker-compose.yml -f docker-compose.app.yml exec -T postgres \
  pg_dump -U aicontrol -d aicontrol > aicontrol-$(date +%F).sql

# Restore into an empty database (stop the API first)
docker compose -f docker-compose.yml -f docker-compose.app.yml stop api frontend
docker compose -f docker-compose.yml -f docker-compose.app.yml exec -T postgres \
  psql -U aicontrol -d aicontrol < aicontrol-2026-10-20.sql
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d
```

`SECRET_KEY` is not stored in the database. Keep a copy of `.env`: with a
different key, every issued agent token and dashboard session fails signature
verification and all agent tokens must be re-issued.

## Monitoring

`GET /health` (port 8001, no authentication):

```json
{"status": "ok", "service": "aicontrol", "database": "ok",
 "audit_wal_pending": 0, "audit_wal_dead_lettered": 0,
 "policy_engine_status": "in_process", "drift_detector_status": "enterprise_only"}
```

- HTTP 503 with `"database": "unreachable"` means the API cannot reach
  Postgres. The container healthcheck uses this endpoint.
- `audit_wal_pending` is the number of audit events written to the local WAL
  that are not yet in Postgres. It is normally 0 to a few. A value that keeps
  growing means events are not being shipped; check the API logs for
  `wal_ship_line_failed`.
- `audit_wal_dead_lettered` counts events that could not be shipped after 25
  attempts since the API started. They are kept in
  `<WAL_DIR>/audit.jsonl.deadletter` (inside the API container: `/app/data/wal/`),
  one JSON object per line with a `_ship_error` field. Alert on a non-zero value.

Logs are JSON lines on stdout when `APP_ENV=production` (collect with your
usual container log driver; compose keeps the last 5 files of 10 MB per
container). Useful event names: `aicontrol_ready`, `wal_ship_line_failed`,
`wal_line_dead_lettered`, `retention_purge_complete`, `retention_purge_failed`,
`retention_purge_skipped`, `slack_message_failed`,
`mcp_upstream_unreachable`.

Support bundle: `bash diagnose.sh`.

## Audit data

Every governed call produces an audit event. The API appends it to a local
write-ahead log and flushes it to disk before responding; a background task
copies it into Postgres within about a second, and trims copied lines out of
the WAL file once it passes 1 MiB. After a crash, unshipped lines are replayed at the next start.

Retention is enforced by a daily purge: Community 7 days, Business 30 days,
Enterprise and Trial 90 days. Export what you need to keep for longer (Enterprise:
`GET /audit-events/export`, or continuous SIEM export on Business+).

## Security notes

- Dashboard sign-ins are JWTs valid for 8 hours. They are checked by
  signature and expiry, not against the user record on each request:
  deactivating, demoting or deleting a user takes full effect when their
  current token expires. Rotate `SECRET_KEY` to end every session at once.
- Agent tokens do not expire. Revoke them from the dashboard Tokens page or
  `scripts/public/revoke_token.py`.
- The `.env` file holds database and signing secrets; keep it out of version
  control and readable only by the operator account.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Dashboard loads but every call fails | `AICONTROL_API_URL` points at an address the browser cannot reach (default `localhost:8001` only works on the host itself). |
| Invite links open `localhost` | `FRONTEND_BASE_URL` not set. |
| Browser console shows CORS errors | Dashboard origin missing from `CORS_ORIGINS`. |
| "Too many attempts" for many users at once | All requests arrive from the proxy's IP; set `FORWARDED_ALLOW_IPS`. |
| API container restarts at boot | Migration failure (see logs), or `SECRET_KEY` unset/`changeme` with `APP_ENV=production`. |
| Review actions return 402 | Reviews require an active Business or Enterprise license. |
