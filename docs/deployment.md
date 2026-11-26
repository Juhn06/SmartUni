# Deployment — SmartUni

> Cập nhật: 19/09/2026  
> Pattern giống **ai.neu.edu.vn / NEUAI** trên cùng server `nct-r750-1-vm3` (101.96.66.222).

## Tóm tắt

Deploy **tự động**: mỗi khi có commit mới trên nhánh `main` của GitHub, cron trên server tự `git fetch` + merge ff-only rồi `docker compose up --build` trong vòng tối đa ~2 phút. **Không** dùng GitHub Actions để SSH vào máy — Actions chỉ là cửa sổ compile.

Production:

| Mục | Giá trị thật trên server |
|---|---|
| Public URL | `https://cfvg.neu.edu.vn` (nginx host → `127.0.0.1:8027`) |
| Host | `nct-r750-1-vm3` / `101.96.66.222` (SSH `:8901`) |
| User | `thaop12` |
| Thư mục clone | `/home/thaop12/SmartUni` |
| Git remote | `git@github-smartuni:thaofami/SmartUni.git` |
| Deploy key | `/home/thaop12/.ssh/smartuni_github` (Host `github-smartuni` trong `~/.ssh/config`) |
| Frontend | `http://127.0.0.1:8027` (`smartuni-frontend`) |
| Backend API | `http://127.0.0.1:8026` (`smartuni-backend`) |
| Script deploy | `/home/thaop12/bin/smartuni-deploy.sh` (**ngoài repo**) |
| Cron | user `thaop12`, `*/2 * * * *` |
| Log | `/home/thaop12/deploy-logs/smartuni-deploy.log` |

Cùng máy với AINEU (`/home/thaop/project/NEUAI`, cron user `thaop`, script `/home/thaop/bin/neuai-deploy.sh`). Hai site **tách user / clone / cron** — không dùng chung script.

## Kiến trúc runtime

```
Public HTTPS:
  https://cfvg.neu.edu.vn  (nginx :443, SSL wildcard NEU)
        │
        └── proxy_pass http://127.0.0.1:8027  smartuni-frontend (Flask)
                      │
                      └── API_BASE_URL ──► :8026 smartuni-backend (Flask + SQLite)
                                              volumes: db, uploads, chroma

Vhost mẫu: `deploy/nginx/cfvg.neu.edu.vn.conf`.
```

So với AINEU: frontend Vite/nginx `:8000` + 3 backend Node; SmartUni chỉ 2 service Flask. Cùng cơ chế cron + `--no-deps` + rollback.

Chi tiết Docker: xem [DOCKER.md](../DOCKER.md).

## Auto-deploy hoạt động thế nào

| Thành phần | Vị trí |
|---|---|
| Script mẫu trong repo | `scripts/smartuni-deploy.sh` |
| Script chạy thật | `/home/thaop12/bin/smartuni-deploy.sh` (copy ra ngoài — `git pull` không ghi đè) |
| Lịch | cron `thaop12`, `*/2 * * * *` (không redirect stdout — script tự ghi log) |
| Lock | `/home/thaop12/.smartuni-deploy.lock` (`flock`) |
| Quarantine commit hỏng | `/home/thaop12/.smartuni-deploy.failed` |
| Nhánh theo dõi | `origin/main` |

Mỗi lần chạy:

1. Kiểm tra đang ở `main` và working tree sạch — nếu không thì **dừng** (không ghi đè sửa tay trên server).
2. `git fetch origin main`. Nếu `HEAD == origin/main` → thoát im lặng.
3. `git merge --ff-only`. Không ff được → dừng.
4. Xem diff để quyết định build lại:

   | File thay đổi | Service build lại |
   |---|---|
   | `frontend/**` | `frontend` |
   | `backend/**` | `backend` |
   | `docker-compose.yml` | cả hai |
   | chỉ `docs/`, `scripts/`, `nghiepvu/`, … | không build |

5. `docker compose up -d --build --no-deps <services>`.  
   `--no-deps` bắt buộc: `frontend` `depends_on: backend` — thiếu flag này sẽ restart backend dù chỉ sửa frontend.
6. Health check tối đa ~120s:
   - Frontend `http://127.0.0.1:8027/login` → **200** (`/` trả 302 vì bắt đăng nhập — không dùng `/` làm health)
   - Backend `http://127.0.0.1:8026/api/metadata` → **200**
7. Fail ở bước 5/6 → **rollback**: `git reset --hard` về commit cũ, build lại, ghi SHA hỏng vào `.smartuni-deploy.failed` để cron không deploy lại cùng commit mỗi 2 phút.
8. Thành công → xóa file quarantine, `docker image prune -f`.

Sau khi một commit bị quarantine, auto-deploy **đứng im** cho đến khi có commit mới hơn trên `main`. Xử lý: push commit sửa (hoặc revert). Muốn ép thử lại đúng commit cũ: xóa `/home/thaop12/.smartuni-deploy.failed`.

Sửa logic deploy: sửa file trong repo **và copy lại** ra `~/bin/` (cron không đọc script trong clone).

## Cài đặt lần đầu trên server

Đã cài trên `thaop12` (19/09/2026). Nếu dựng lại máy:

```bash
# 1) Clone
mkdir -p /home/thaop12
cd /home/thaop12
git clone git@github-smartuni:thaofami/SmartUni.git SmartUni
cd SmartUni
git checkout main

# 2) Env backend
# chỉnh backend/.env (SECRET / LLM keys)

# 3) Chạy lần đầu
docker compose up -d --build

# 4) Cài script deploy ngoài repo
mkdir -p /home/thaop12/bin /home/thaop12/deploy-logs
cp scripts/smartuni-deploy.sh /home/thaop12/bin/smartuni-deploy.sh
chmod +x /home/thaop12/bin/smartuni-deploy.sh

# 5) Cron mỗi 2 phút (user thaop12)
crontab -e
# thêm:
# # SmartUni auto-deploy: poll origin/main moi 2 phut
# */2 * * * * /home/thaop12/bin/smartuni-deploy.sh
```

### Deploy key GitHub

Đã có: `~/.ssh/smartuni_github` + `Host github-smartuni` trỏ `github.com`. Public key gắn Deploy keys (read-only) trên repo `thaofami/SmartUni`.

```
Host github-smartuni
  HostName github.com
  User git
  IdentityFile ~/.ssh/smartuni_github
  IdentitiesOnly yes
```

Remote: `git@github-smartuni:thaofami/SmartUni.git`.

## Thao tác thường dùng

Xem log:

```bash
tail -50 /home/thaop12/deploy-logs/smartuni-deploy.log
```

Ép deploy ngay (không đợi cron):

```bash
/home/thaop12/bin/smartuni-deploy.sh
```

Trạng thái container:

```bash
cd /home/thaop12/SmartUni && docker compose ps
```

Tạm dừng auto-deploy:

```bash
crontab -l | sed 's|^\*/2|#*/2|' | crontab -
```

Bật lại:

```bash
crontab -l | sed 's|^#\*/2|*/2|' | crontab -
```

Rollback thủ công:

```bash
cd /home/thaop12/SmartUni
git reset --hard <commit>
docker compose up -d --build
```

> Rollback thủ công làm `HEAD` lệch `origin/main`. Cron lần sau sẽ lại kéo commit mới hơn. Muốn giữ rollback: tắt cron, hoặc revert trên GitHub rồi để cron kéo.

## CI (GitHub Actions)

Workflow `.github/workflows/ci.yml` chạy khi push/PR vào `main`: compile Python frontend/backend + `docker compose config`. Đây là **cửa sổ build** — bắt lỗi cú pháp trước khi cron trên server kéo commit.

Auto-deploy vẫn do cron trên server; Actions **không** SSH vào máy production (giống NEUAI / ai.neu.edu.vn).

## Nợ kỹ thuật / lưu ý

- Không có test E2E; health check chỉ bắt app chết, không bắt lỗi logic.
- Build ngay trên máy production (giống NEUAI) — tốn CPU/RAM lúc deploy.
- `RESET_STAFF_PASSWORDS=true` mặc định trong compose: mỗi lần restart backend, mật khẩu STAFF về `123!`. Production nên đặt `false`.
- Ports `8026`/`8027` đang publish ra ngoài; nginx host reverse-proxy `cfvg.neu.edu.vn`.
- Working tree trên server **phải sạch**. Sửa tay trên `/home/thaop12/SmartUni` sẽ làm cron dừng cho đến khi stash/revert.
- Code chưa push lên `main` thì cron **không** kéo về (local dirty / chưa commit không deploy).
