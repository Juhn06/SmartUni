# Docker Deployment

## Quick Start

```bash
docker compose build --no-cache
docker compose up -d
```

- **Public:** https://cfvg.neu.edu.vn (nginx → `:8027`)
- **Frontend:** http://localhost:8027 (hoặc IP server:8027)
- **Backend API:** http://localhost:8026

## Auto-deploy (giống NEUAI)

Production (`thaop12` trên cùng máy với ai.neu.edu.vn): cron mỗi 2 phút → `git fetch` + `docker compose up --build --no-deps` khi `main` có commit mới. Script chạy thật: `/home/thaop12/bin/smartuni-deploy.sh`. Hướng dẫn: **[docs/deployment.md](docs/deployment.md)**.

## Menu NAV trống trên server nhưng local có?

Frontend Docker **không** chứa `backend/rbac.py`. Menu phải lấy từ API:

`GET http://backend:8026/users/<id>/access?lang=vi` → field `nav`

Nếu image cũ / frontend chưa rebuild:

```bash
docker compose build --no-cache frontend backend
docker compose up -d
docker compose logs frontend --tail 30
docker compose exec frontend python -c "import os; print(os.environ.get('API_BASE_URL'))"
```

`API_BASE_URL` trong container phải là `http://backend:8026` (không dùng `127.0.0.1`).

## Login staff không được trên server?

Nguyên nhân thường gặp:

1. **Image cũ** — Dockerfile trước đây không copy đủ `seed_org.py` / `rbac.py`… → thiếu seed tài khoản.
2. **Volume DB cũ** — Docker volume `backend_db` giữ DB riêng, không dùng file `website.db` local.

Khắc phục:

```bash
docker compose build --no-cache
docker compose up -d
docker compose logs backend --tail 50
```

Mặc định `RESET_STAFF_PASSWORDS=true`: mỗi lần backend start, mật khẩu STAFF về `123!`.

Tắt reset (giữ mật khẩu đã đổi):

```yaml
environment:
  - RESET_STAFF_PASSWORDS=false
```

Nếu vẫn lỗi, xóa volume DB rồi seed lại (**mất dữ liệu** trong volume):

```bash
docker compose down
docker volume ls
docker volume rm <tên_volume_backend_db>
docker compose up -d --build
```

## Commands

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start services in background |
| `docker compose down` | Stop and remove containers |
| `docker compose logs -f` | View logs |
| `docker compose build --no-cache` | Rebuild images |

## Environment Variables

| Variable | Service | Default |
|----------|---------|---------|
| `API_BASE_URL` | frontend | `http://backend:8026` |
| `SECRET_KEY` | frontend | `dev-secret-key` |
| `PORT` | both | 8026 / 8027 |
| `FLASK_DEBUG` | both | `false` |
| `DB_PATH` | backend | `./db/website.db` |
| `RESET_STAFF_PASSWORDS` | backend | `true` |

## Data Persistence

- **SQLite database:** Docker volume `backend_db`
- **Uploads:** Docker volume `backend_uploads`
- **Bulk import data:** `backend/data` mounted to `/app/data`
