#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MAESTRO_DIR="$ROOT_DIR/app/maestro"
CASE="${1:-all}"
PYTHON="${MAESTRO_PYTHON:-$ROOT_DIR/.venv/bin/python}"
DEVICE="${MAESTRO_DEVICE:-emulator-5554}"
OUTPUT_DIR="$MAESTRO_DIR/results/$(date +%Y%m%d-%H%M%S)-$$"
COMPOSE=(docker compose -p vard-maestro -f "$MAESTRO_DIR/compose.yaml")

# npm can run with a different PATH than an interactive terminal. Keep the
# caller's tools first and fall back to standard local installation paths.
add_tool_path() {
  [[ -d "$1" ]] || return 0
  case ":$PATH:" in
    *":$1:"*) ;;
    *) export PATH="$PATH:$1" ;;
  esac
}
if [[ -n "${npm_node_execpath:-}" && -x "$npm_node_execpath" ]]; then
  add_tool_path "$(dirname "$npm_node_execpath")"
fi
add_tool_path /usr/local/bin
add_tool_path /opt/homebrew/bin
add_tool_path /Applications/Docker.app/Contents/Resources/bin
add_tool_path "$HOME/.docker/bin"
add_tool_path "$HOME/.maestro/bin"
[[ -z "${ANDROID_HOME:-}" ]] || add_tool_path "$ANDROID_HOME/platform-tools"
[[ -z "${ANDROID_SDK_ROOT:-}" ]] || add_tool_path "$ANDROID_SDK_ROOT/platform-tools"
add_tool_path "$HOME/Library/Android/sdk/platform-tools"
add_tool_path "$HOME/Android/Sdk/platform-tools"

case "$CASE" in
  all) FLOWS=(auth/email-validation.yaml auth/login-validation.yaml auth/signup.yaml navigation/tabs-and-logout.yaml workspace/create.yaml workspace/invite.yaml workspace/accept-invite.yaml workspace/camera-actions.yaml) ;;
  email) FLOWS=(auth/email-validation.yaml) ;;
  login) FLOWS=(auth/login-validation.yaml) ;;
  signup) FLOWS=(auth/signup.yaml) ;;
  navigation) FLOWS=(navigation/tabs-and-logout.yaml) ;;
  workspace) FLOWS=(workspace/create.yaml) ;;
  invite) FLOWS=(workspace/invite.yaml) ;;
  accept) FLOWS=(workspace/accept-invite.yaml) ;;
  camera) FLOWS=(workspace/camera-actions.yaml) ;;
  *) echo 'Uso: npm run test:e2e -- [all|email|login|signup|navigation|workspace|invite|accept|camera]' >&2; exit 2 ;;
esac
for command in docker maestro adb node curl; do
  command -v "$command" >/dev/null || { echo "Comando ausente: $command" >&2; exit 1; }
done
docker info >/dev/null 2>&1 || {
  echo 'Docker instalado, mas o daemon não está acessível. Inicie o Docker Desktop e tente novamente.' >&2
  exit 1
}
docker compose version >/dev/null 2>&1 || {
  echo 'Docker Compose indisponível. Instale o plugin Compose ou atualize o Docker Desktop.' >&2
  exit 1
}
[[ -x "$PYTHON" ]] || { echo 'Instale requirements-api.txt em .venv ou defina MAESTRO_PYTHON.' >&2; exit 1; }
[[ -f "$ROOT_DIR/app/node_modules/expo/bin/cli" ]] || { echo 'Execute npm ci em app/ antes de testar.' >&2; exit 1; }
adb -s "$DEVICE" get-state >/dev/null
adb -s "$DEVICE" shell pm path com.devsilogix.vard | grep -q package: || {
  echo 'Instale o development build: cd app && npx expo run:android' >&2; exit 1;
}
# Fail before taking ownership of any resources already in use.
"$PYTHON" - <<'PY'
import socket
for port in (18000, 18081, 55432):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'Porta {port} ocupada; encerre a execucao anterior antes de testar.')
PY
mkdir -p "$OUTPUT_DIR"
API_PID=''
METRO_PID=''
COMPOSE_STARTED=0
cleanup() {
  status=$?
  trap - EXIT
  [[ -z "$METRO_PID" ]] || kill "$METRO_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || kill "$API_PID" 2>/dev/null || true
  if [[ "$COMPOSE_STARTED" == 1 ]]; then
    "${COMPOSE[@]}" down >"$OUTPUT_DIR/cleanup.log" 2>&1 || true
  fi
  adb -s "$DEVICE" reverse --remove tcp:18000 >/dev/null 2>&1 || true
  adb -s "$DEVICE" reverse --remove tcp:18081 >/dev/null 2>&1 || true
  echo "Relatorios: $OUTPUT_DIR"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Override .env integrations; use only the dedicated, ephemeral database.
export DATABASE_URL='postgresql://vard_maestro:local-maestro-only@127.0.0.1:55432/vard_maestro'
export JWT_SECRET_KEY='maestro-local-disposable-test-secret'
export APP_ENV=test FALL_MONITOR_ENABLED=false REDIS_URL=''
export ONESIGNAL_APP_ID='' ONESIGNAL_API_KEY='' SENDGRID_API_KEY='' SENDGRID_FROM_EMAIL=''
export VARD_MAESTRO=1 EXPO_NO_DOTENV=1 EXPO_PUBLIC_ONESIGNAL_APP_ID=''
export EXPO_PUBLIC_API_BASE_URL='http://127.0.0.1:18000'
export CI=1
cd "$ROOT_DIR"
COMPOSE_STARTED=1
"${COMPOSE[@]}" up -d --wait >"$OUTPUT_DIR/database.log" 2>&1
"$PYTHON" -m scripts.migrate >"$OUTPUT_DIR/migrations.log" 2>&1
"$PYTHON" -m uvicorn api.main:app --host 127.0.0.1 --port 18000 >"$OUTPUT_DIR/api.log" 2>&1 &
API_PID=$!
wait_http() {
  local url="$1" pid="$2"
  for ((attempt=0; attempt<90; attempt++)); do
    if curl --silent --fail "$url" >/dev/null; then return 0; fi
    kill -0 "$pid" 2>/dev/null || { echo "Processo encerrou; consulte $OUTPUT_DIR" >&2; return 1; }
    sleep 1
  done
  echo "Timeout aguardando $url" >&2
  return 1
}
wait_http http://127.0.0.1:18000/health "$API_PID"
"$PYTHON" "$MAESTRO_DIR/fixtures.py" seed
adb -s "$DEVICE" reverse tcp:18000 tcp:18000
adb -s "$DEVICE" reverse tcp:18081 tcp:18081
cd "$ROOT_DIR/app"
node node_modules/expo/bin/cli start --dev-client --localhost --clear --port 18081 >"$OUTPUT_DIR/metro.log" 2>&1 &
METRO_PID=$!
wait_http http://127.0.0.1:18081/status "$METRO_PID"
adb -s "$DEVICE" shell am force-stop com.devsilogix.vard
adb -s "$DEVICE" shell am start -W -a android.intent.action.VIEW -d 'vard://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A18081' com.devsilogix.vard >"$OUTPUT_DIR/launch.log"
maestro --device "$DEVICE" test "$MAESTRO_DIR/shared/prepare-dev-client.yaml" --debug-output "$OUTPUT_DIR/prepare"
for flow in "${FLOWS[@]}"; do
  name="$(basename "$flow" .yaml)"
  maestro --device "$DEVICE" test "$MAESTRO_DIR/$flow" \
    -e MAESTRO_EMAIL=maestro.login@example.com \
    -e MAESTRO_SIGNUP_EMAIL=maestro.signup@example.com \
    -e MAESTRO_INVITE_EMAIL=maestro.invite@example.com \
    -e MAESTRO_ACCEPT_EMAIL=maestro.invited@example.com \
    -e 'MAESTRO_CAMERA_NAME=Camera Maestro' \
    -e 'MAESTRO_WORKSPACE_NAME=Casa Maestro' \
    -e 'MAESTRO_PASSWORD=MaestroLocal123!' \
    --format junit --output "$OUTPUT_DIR/$name.xml" --debug-output "$OUTPUT_DIR/$name"
done
"$PYTHON" "$MAESTRO_DIR/fixtures.py" verify "$CASE"
