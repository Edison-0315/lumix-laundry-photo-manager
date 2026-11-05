#!/bin/bash
set -euo pipefail
runtime="$TARGET_BUILD_DIR/$UNLOCALIZED_RESOURCES_FOLDER_PATH/Python"
if [ ! -x "$runtime/bin/python3" ]; then
  echo 'error: Missing arm64 runtime. Run: /usr/bin/python3 -I -B macos/Runtime/prepare_runtime.py' >&2
  exit 1
fi
if [ "${CODE_SIGNING_ALLOWED:-YES}" = NO ]; then exit 0; fi
identity="${EXPANDED_CODE_SIGN_IDENTITY:--}"
while IFS= read -r -d '' binary; do
  /usr/bin/codesign --force --sign "$identity" "$binary"
done < <(/usr/bin/find "$runtime" -type f \( -name '*.so' -o -name '*.dylib' -o -name 'python3.12' \) -print0)
