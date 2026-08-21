#!/bin/bash
# Drive install.command the way a buyer does, against a throwaway HOME, and
# assert on what actually lands on disk. Not a Mac -- but it is the real script,
# really run, and it catches everything except Mac-specific system behaviour
# (Gatekeeper, Finder double-click, bash 3.2 quirks).
set -u
BASE="${1:-${TMPDIR:-/tmp}/ftb-bundle-check-$$}"   # a fresh working dir
FAIL=0

ok()   { echo "  OK   $1"; }
bad()  { echo "  BAD  $1"; FAIL=1; }

check() {           # check <desc> <path> <should-exist:1|0>
  if [ -e "$2" ]; then [ "$3" = 1 ] && ok "$1" || bad "$1 (still present: $2)"
  else                 [ "$3" = 0 ] && ok "$1" || bad "$1 (missing: $2)"; fi
}

run_bundle() {      # run_bundle <label> <zip> <top> <is_pro>
  local label="$1" zip="$2" top="$3" pro="$4"
  local dir="$BASE/$label"
  mkdir -p "$dir" && (cd "$dir" && unzip -oq "$zip") || { bad "$label: unzip"; return; }

  export HOME="$dir/home"
  local BL="$HOME/Library/Application Support/Blender"
  local AI="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
  mkdir -p "$BL/4.2/scripts/addons" "$BL/4.5/scripts/addons"
  # a buyer who already had the free add-on
  mkdir -p "$BL/4.5/scripts/addons/fusion_to_blender_addon_blender"

  echo; echo "=== $label ==="
  bash -n "$dir/$top/install.command" && ok "syntax" || bad "syntax"
  [ -x "$dir/$top/install.command" ] && ok "executable after unzip" \
                                     || bad "executable after unzip"

  local out
  out=$(cd "$dir/$top" && bash ./install.command install 2>&1)

  check "fusion add-in installed" "$AI/fusion_to_blender_addon_fusion/exporter.py" 1
  check "no editor config shipped" "$AI/fusion_to_blender_addon_fusion/.vscode" 0

  if [ "$pro" = 1 ]; then
    check "bridge_pro in 4.2"  "$BL/4.2/scripts/addons/bridge_pro/__init__.py" 1
    check "bridge_pro in 4.5"  "$BL/4.5/scripts/addons/bridge_pro/__init__.py" 1
    check "vendored core"      "$BL/4.5/scripts/addons/bridge_pro/core/handler.py" 1
    check "old free add-on removed" "$BL/4.5/scripts/addons/fusion_to_blender_addon_blender" 0
    echo "$out" | grep -q 'enable$' ; :
    if echo "$out" | grep -q '"Fusion to Blender Bridge"'; then ok "tells buyer the right add-on name"
    else bad "tells buyer the right add-on name"; fi
    if echo "$out" | grep -q '"Fusion to Blender Lite"'; then bad "still says Lite"; else ok "no stray 'Lite'"; fi
  else
    check "free add-on in 4.2" "$BL/4.2/scripts/addons/fusion_to_blender_addon_blender/__init__.py" 1
    check "free add-on in 4.5" "$BL/4.5/scripts/addons/fusion_to_blender_addon_blender/__init__.py" 1
    check "no bridge_pro"      "$BL/4.5/scripts/addons/bridge_pro" 0
    if echo "$out" | grep -q '"Fusion to Blender Lite"'; then ok "names the free add-on"
    else bad "names the free add-on"; fi
  fi

  # Uninstall must leave nothing of ours behind.
  local uout
  uout=$(cd "$dir/$top" && bash ./install.command uninstall 2>&1)
  local dupes
  dupes=$(echo "$uout" | grep -c "addons/bridge_pro$")
  if [ "$pro" = 1 ] && [ "$dupes" -gt 1 ]; then bad "bridge_pro listed $dupes times"; else ok "no duplicated lines"; fi

  check "fusion add-in removed" "$AI/fusion_to_blender_addon_fusion" 0
  check "bridge_pro removed"    "$BL/4.5/scripts/addons/bridge_pro" 0
  check "free add-on removed"   "$BL/4.5/scripts/addons/fusion_to_blender_addon_blender" 0
}

R="C:/Users/inspa/claude"
run_bundle paid "$R/bridge-pro/bridge_pro_installer.zip" bridge_pro_installer 1
run_bundle free "$R/fusion to blender bridge/fusion_to_blender_bridge_installer.zip" \
                fusion_to_blender_bridge_installer 0

echo
[ "$FAIL" = 0 ] && echo "ALL CHECKS PASS" || echo "FAILURES ABOVE"
exit "$FAIL"
