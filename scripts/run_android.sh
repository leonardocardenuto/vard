#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../app" && pwd)"
cd "$APP_DIR"

# Use a supported LTS JDK even when the system defaults to a newer Java.
use_jdk() {
  local candidate="${1:-}"
  [[ -x "$candidate/bin/java" ]] || return 1
  local major
  major=$("$candidate/bin/java" -version 2>&1 | sed -nE 's/.*version "([0-9]+).*/\1/p' | head -n 1)
  [[ "$major" == 17 || "$major" == 21 ]] || return 1
  export JAVA_HOME="$candidate"
}

JDK_CANDIDATES=("${JAVA_HOME:-}")
if [[ "$(uname -s)" == Darwin ]]; then
  JDK_CANDIDATES+=(
    "$(/usr/libexec/java_home -v 21 2>/dev/null || true)"
    "$(/usr/libexec/java_home -v 17 2>/dev/null || true)"
    "/Applications/Android Studio.app/Contents/jbr/Contents/Home"
    "$HOME/Applications/Android Studio.app/Contents/jbr/Contents/Home"
  )
else
  JDK_CANDIDATES+=("/opt/android-studio/jbr" "$HOME/android-studio/jbr")
fi
if command -v java >/dev/null 2>&1; then
  JDK_CANDIDATES+=("$(java -XshowSettings:properties -version 2>&1 | sed -n 's/^[[:space:]]*java.home = //p')")
fi

JDK_FOUND=false
for candidate in "${JDK_CANDIDATES[@]}"; do
  if use_jdk "$candidate"; then
    JDK_FOUND=true
    break
  fi
done
if [[ "$JDK_FOUND" != true ]]; then
  echo 'Defina JAVA_HOME para um JDK 17 ou 21 (o JDK 21 do Android Studio também funciona).' >&2
  exit 1
fi
export PATH="$JAVA_HOME/bin:$PATH"
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$APP_DIR/.gradle-local}"

if [[ -z "${ANDROID_HOME:-}" ]]; then
  for candidate in "${ANDROID_SDK_ROOT:-}" "$HOME/Library/Android/sdk" "$HOME/Android/Sdk"; do
    if [[ -d "$candidate/platform-tools" ]]; then
      export ANDROID_HOME="$candidate"
      break
    fi
  done
fi
if [[ -n "${ANDROID_HOME:-}" ]]; then
  export PATH="$ANDROID_HOME/platform-tools:$PATH"
fi

echo "Usando JAVA_HOME=$JAVA_HOME"
exec npx expo run:android "$@"
