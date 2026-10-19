#!/usr/bin/env bash
set -euo pipefail

# Simulates the real sensor stream; no production test/bypass endpoint.
device="${1:-emulator-5554}"
original="$(adb -s "$device" emu sensor get acceleration | sed -n 's/^acceleration = //p' | tr -d '\r')"
restore() { adb -s "$device" emu sensor set acceleration "${original:-0:9.81:0}" >/dev/null || true; }
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
echo 'Prepare o perfil Idoso, ative a proteção e mantenha as notificações permitidas.'
adb -s "$device" emu sensor set acceleration 0:9.81:0
sleep 2
adb -s "$device" emu sensor set acceleration 0:0:0
sleep 0.3
adb -s "$device" emu sensor set acceleration 0:0:32
sleep 0.15
adb -s "$device" emu sensor set acceleration 0:0:9.81
echo 'Impacto simulado. Aguarde a confirmação; cancele em até 20s para não enviar um alerta.'
sleep 26
