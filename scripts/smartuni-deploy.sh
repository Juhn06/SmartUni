#!/usr/bin/env bash
#
# SmartUni auto-deploy (cùng pattern với /home/thaop/bin/neuai-deploy.sh trên ai.neu.edu.vn)
# Poll origin/main; nếu có commit mới thì fast-forward, build lại đúng service
# bị ảnh hưởng, health check, và tự rollback nếu hỏng.
#
# Cài NGOÀI repo rồi gắn cron (không để git pull ghi đè):
#   cp scripts/smartuni-deploy.sh /home/thaop12/bin/smartuni-deploy.sh
#   chmod +x /home/thaop12/bin/smartuni-deploy.sh
#   crontab: */2 * * * * /home/thaop12/bin/smartuni-deploy.sh
#
# Log: /home/thaop12/deploy-logs/smartuni-deploy.log
#
set -uo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

REPO=/home/thaop12/SmartUni
BRANCH=main
LOGDIR=/home/thaop12/deploy-logs
LOG="$LOGDIR/smartuni-deploy.log"
LOCK=/home/thaop12/.smartuni-deploy.lock
FAILED_FILE=/home/thaop12/.smartuni-deploy.failed
# / trả 302 (redirect login); /login phải 200. Backend metadata phải 200.
WEB_URL=http://127.0.0.1:8027/login
API_URL=http://127.0.0.1:8026/api/metadata
HEALTH_TRIES=30
HEALTH_INTERVAL=4

export GIT_SSH_COMMAND="ssh -i /home/thaop12/.ssh/smartuni_github -o IdentitiesOnly=yes -o BatchMode=yes"

mkdir -p "$LOGDIR"
log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" >>"$LOG"; }

# Cắt log khi vượt 5MB, giữ lại 2MB cuối
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ]; then
  tail -c 2000000 "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

# Không cho hai lần deploy chồng nhau
exec 200>"$LOCK"
flock -n 200 || exit 0

cd "$REPO" || { log "FATAL: không vào được $REPO"; exit 1; }

CUR_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CUR_BRANCH" != "$BRANCH" ]; then
  log "FATAL: server đang ở nhánh '$CUR_BRANCH', mong đợi '$BRANCH'. Bỏ qua để không deploy nhầm."
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  log "FATAL: working tree bẩn — có người sửa file trực tiếp trên server. Bỏ qua để không ghi đè."
  git status --short >>"$LOG"
  exit 1
fi

if ! git fetch --quiet origin "$BRANCH" 2>>"$LOG"; then
  log "ERROR: git fetch thất bại (key GitHub hỏng? mạng?)."
  exit 1
fi

PREV=$(git rev-parse HEAD)
NEXT=$(git rev-parse "origin/$BRANCH")

# Không có gì mới -> thoát im lặng, không ghi log (cron chạy 720 lần/ngày)
[ "$PREV" = "$NEXT" ] && exit 0

# Commit này đã deploy hỏng và bị rollback rồi -> không thử lại, tránh lặp vô hạn.
if [ -f "$FAILED_FILE" ] && [ "$(cat "$FAILED_FILE" 2>/dev/null)" = "$NEXT" ]; then
  exit 0
fi

log "════ COMMIT MỚI: ${PREV:0:7} -> ${NEXT:0:7} ════"
git log --oneline "$PREV..$NEXT" >>"$LOG" 2>&1

if ! git merge --ff-only "origin/$BRANCH" >>"$LOG" 2>&1; then
  log "ERROR: không fast-forward được (nhánh main đã bị force-push / rewrite?). Dừng, không deploy."
  exit 1
fi

CHANGED=$(git diff --name-only "$PREV" "$NEXT")
SERVICES=""
echo "$CHANGED" | grep -q '^frontend/' && SERVICES="$SERVICES frontend"
echo "$CHANGED" | grep -q '^backend/'  && SERVICES="$SERVICES backend"
# Đổi compose thì dựng lại tất cả
echo "$CHANGED" | grep -qE '^docker-compose\.ya?ml$' && SERVICES="frontend backend"

if [ -z "$SERVICES" ]; then
  log "Không đụng frontend/ backend/ compose (chỉ docs, scripts, …) — cập nhật code xong, bỏ qua build."
  exit 0
fi

log "Build lại:$SERVICES"

rollback() {
  local reason="$1"
  log "ERROR: $reason — ROLLBACK về ${PREV:0:7}"
  git reset --hard "$PREV" >>"$LOG" 2>&1
  if docker compose up -d --build --no-deps $SERVICES >>"$LOG" 2>&1; then
    log "Đã rollback xong. Hệ thống trở lại ${PREV:0:7}."
  else
    log "NGUY HIỂM: rollback CŨNG thất bại. Cần người vào xử lý ngay."
  fi
  echo "$NEXT" >"$FAILED_FILE"
  log "Đã cách ly ${NEXT:0:7}. Auto-deploy tạm dừng cho tới khi có commit mới trên $BRANCH."
  log "Muốn thử lại commit này: xoá $FAILED_FILE"
  exit 1
}

if ! docker compose up -d --build --no-deps $SERVICES >>"$LOG" 2>&1; then
  rollback "build hoặc khởi động container thất bại"
fi

OK=0
CODE_WEB=000
CODE_API=000
for _ in $(seq 1 "$HEALTH_TRIES"); do
  sleep "$HEALTH_INTERVAL"
  CODE_WEB=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$WEB_URL" 2>/dev/null || echo 000)
  CODE_API=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$API_URL" 2>/dev/null || echo 000)
  if [ "$CODE_WEB" = "200" ] && [ "$CODE_API" = "200" ]; then
    OK=1
    break
  fi
done

[ "$OK" = "1" ] || rollback "health check FAIL sau $((HEALTH_TRIES * HEALTH_INTERVAL))s (web=$CODE_WEB api=$CODE_API)"

log "OK: deploy thành công ${NEXT:0:7} (web=$CODE_WEB api=$CODE_API)"
rm -f "$FAILED_FILE"

docker image prune -f >>"$LOG" 2>&1
log "Đã dọn image cũ."
