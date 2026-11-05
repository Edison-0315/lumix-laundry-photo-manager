#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-run}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="LaundryPhotoManager"
APP_BUNDLE="$ROOT_DIR/build/Build/Products/Debug/$APP_NAME.app"
case "$MODE" in run|--debug|--logs|--telemetry|--verify) ;; *) echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2; exit 2;; esac
/usr/bin/python3 -I -B "$ROOT_DIR/macos/Runtime/prepare_runtime.py"
/usr/bin/python3 -I -B "$ROOT_DIR/macos/Models/prepare_models.py"
pkill -x "$APP_NAME" >/dev/null 2>&1 || true
xcodebuild -quiet -project "$ROOT_DIR/macos/LaundryPhotoManager.xcodeproj" -scheme "$APP_NAME" -configuration Debug -destination 'platform=macOS,arch=arm64' -derivedDataPath "$ROOT_DIR/build" build CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES
case "$MODE" in
 run) /usr/bin/open -n "$APP_BUNDLE";;
 --debug) lldb -- "$APP_BUNDLE/Contents/MacOS/$APP_NAME";;
 --logs|--telemetry) /usr/bin/open -n "$APP_BUNDLE"; /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\"";;
 --verify) /usr/bin/open -n "$APP_BUNDLE"; sleep 1; pgrep -x "$APP_NAME" >/dev/null; echo 'Build and process launch verified';;
esac
