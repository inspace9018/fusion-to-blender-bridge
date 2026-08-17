#!/bin/bash
# =============================================================================
#  Fusion to Blender Lite - macOS Installer
# -----------------------------------------------------------------------------
#  WHAT THIS SCRIPT DOES (plain language):
#    It sets up the bridge that syncs Fusion 360 models into Blender by copying
#    TWO add-on folders into the right places:
#      1) Fusion 360 add-in -> ~/Library/Application Support/Autodesk/.../AddIns
#      2) Blender add-on     -> ~/Library/Application Support/Blender/<ver>/scripts/addons
#    It does NOT touch anything else on your Mac, does NOT need the internet,
#    and does NOT require admin rights. Uninstall removes ONLY those two folders.
#
#    If macOS blocks this file, right-click it > Open (or run once in Terminal:
#    chmod +x install.command).
# =============================================================================
set -u
cd "$(dirname "$0")"
ROOT="$(pwd)"

# Optional non-interactive mode: ./install.command install | update | uninstall
MODE="${1:-}"

FUSION_NAME="fusion_to_blender_addon_fusion"
BLENDER_NAME="fusion_to_blender_addon_blender"
FUSION_SRC="$ROOT/$FUSION_NAME"
BLENDER_SRC="$ROOT/$BLENDER_NAME"

FUSION_ADDINS="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
FUSION_DEST="$FUSION_ADDINS/$FUSION_NAME"
BLENDER_BASE="$HOME/Library/Application Support/Blender"

# Bridge Pro bundle: the paid download carries a third folder beside the two
# free ones. Absent in the free bundle, and then every step below skips it.
PRO_NAME="bridge_pro"
PRO_SRC="$ROOT/$PRO_NAME"
HAS_PRO=0
[ -d "$PRO_SRC" ] && HAS_PRO=1

pause() { [ -n "$MODE" ] && return 0; echo; read -n 1 -s -r -p "  Press any key to continue..."; echo; }

# clean_replace SRC DEST EXPECTED_NAME — remove dest (guarded by name) then copy
clean_replace() {
  local src="$1" dest="$2" name="$3"
  [ "$(basename "$dest")" = "$name" ] || return 1     # guard: never wipe a parent
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -R "$src/." "$dest/" || return 1
  return 0
}

# remove_dir DEST EXPECTED_NAME — safe rm guarded by folder name
remove_dir() {
  local dest="$1" name="$2"
  [ "$(basename "$dest")" = "$name" ] || return 1
  [ -d "$dest" ] || return 1
  rm -rf "$dest"
  [ -d "$dest" ] && return 1
  return 0
}

do_install() {
  clear
  echo
  echo "  Installing Fusion to Blender Lite..."
  echo
  if [ ! -d "$FUSION_SRC" ] || [ ! -d "$BLENDER_SRC" ]; then
    echo "  [!] Missing add-on folder(s) next to this installer."
    echo "      Re-extract the downloaded ZIP and run install.command from inside it."
    pause; return
  fi

  local fail=0

  echo "  [1/2] Fusion 360 add-in"
  mkdir -p "$FUSION_ADDINS"
  if clean_replace "$FUSION_SRC" "$FUSION_DEST" "$FUSION_NAME"; then
    echo "        -> OK  ($FUSION_DEST)"
  else
    echo "        -> FAILED"; fail=1
  fi

  if [ "$HAS_PRO" -eq 1 ]; then echo "  [2/3] Blender add-on"; else echo "  [2/2] Blender add-on"; fi
  local count=0
  if [ -d "$BLENDER_BASE" ]; then
    for vdir in "$BLENDER_BASE"/*/; do
      [ -d "$vdir" ] || continue
      local dest="${vdir}scripts/addons/$BLENDER_NAME"
      mkdir -p "${vdir}scripts/addons"
      if clean_replace "$BLENDER_SRC" "$dest" "$BLENDER_NAME"; then
        echo "        -> $(basename "$vdir")  OK"; count=$((count+1))
      else
        echo "        -> $(basename "$vdir")  FAILED"; fail=1
      fi
    done
  fi
  if [ "$count" -eq 0 ]; then
    echo "        -> No Blender user folder found automatically."
    echo "           Open Blender once, or install via Blender:"
    echo "           Edit > Preferences > Add-ons > Install from Disk"
    echo "           pointing at the $BLENDER_NAME folder."
  fi

  if [ "$HAS_PRO" -eq 1 ]; then
    echo "  [3/3] Bridge Pro"
    pcount=0
    if [ -d "$BLENDER_BASE" ]; then
      for vdir in "$BLENDER_BASE"/*/; do
        [ -d "$vdir" ] || continue
        pdest="${vdir}scripts/addons/$PRO_NAME"
        mkdir -p "${vdir}scripts/addons"
        if clean_replace "$PRO_SRC" "$pdest" "$PRO_NAME"; then
          echo "        -> $(basename "$vdir")  OK"; pcount=$((pcount+1))
        else
          echo "        -> $(basename "$vdir")  FAILED"; fail=1
        fi
      done
    fi
    if [ "$pcount" -eq 0 ]; then
      echo "        -> No Blender user folder found automatically."
      echo "           Install via Blender: Edit > Preferences > Add-ons >"
      echo "           Install from Disk, pointing at the $PRO_NAME folder."
    fi
  fi

  echo
  if [ "$fail" -eq 0 ]; then echo "  [OK] Done."; else
    echo "  [!] Finished with errors. Close Fusion/Blender and run Update/Repair."
  fi
  echo
  echo "  NEXT STEPS:"
  echo "    - Fusion 360: Utilities (or Tools) > Add-Ins > \"Scripts and Add-Ins\""
  echo "                  > Add-Ins tab > select \"$FUSION_NAME\" > Run"
  echo "    - Blender:    Edit > Preferences > Add-ons > enable"
  echo "                  \"Fusion to Blender Lite\" (then restart Blender)"
  echo "    - Then in Blender just press Sync. Connection is automatic."
  pause
}

do_uninstall() {
  clear
  echo
  echo "  Uninstall - removes ONLY these two folders:"
  echo "    - $FUSION_DEST"
  echo "    - $BLENDER_BASE/<version>/scripts/addons/$BLENDER_NAME"
  echo
  if [ -z "$MODE" ]; then
    read -r -p "  Remove Fusion to Blender Lite? (y/N): " ok
    case "$ok" in [yY]) ;; *) return;; esac
  fi

  echo
  if [ "$HAS_PRO" -eq 1 ]; then echo "  [1/3] Fusion 360 add-in"; else echo "  [1/2] Fusion 360 add-in"; fi
  if remove_dir "$FUSION_DEST" "$FUSION_NAME"; then echo "        -> removed"; else echo "        -> not found"; fi

  if [ "$HAS_PRO" -eq 1 ]; then echo "  [2/3] Blender add-on"; else echo "  [2/2] Blender add-on"; fi
  local rm=0
  if [ -d "$BLENDER_BASE" ]; then
    for vdir in "$BLENDER_BASE"/*/; do
      local dest="${vdir}scripts/addons/$BLENDER_NAME"
      if [ -d "$dest" ] && remove_dir "$dest" "$BLENDER_NAME"; then
        echo "        -> $(basename "$vdir")  removed"; rm=$((rm+1))
      fi
    done
  fi
  [ "$rm" -eq 0 ] && echo "        -> none found"

  if [ "$HAS_PRO" -eq 1 ]; then
    echo "  [3/3] Bridge Pro"
    prm=0
    if [ -d "$BLENDER_BASE" ]; then
      for vdir in "$BLENDER_BASE"/*/; do
        pdest="${vdir}scripts/addons/$PRO_NAME"
        if [ -d "$pdest" ] && remove_dir "$pdest" "$PRO_NAME"; then
          echo "        -> $(basename "$vdir")  removed"; prm=$((prm+1))
        fi
      done
    fi
    [ "$prm" -eq 0 ] && echo "        -> none found"
  fi
  echo
  echo "  [OK] Uninstall complete. (Disable it in Blender if still listed.)"
  pause
}

case "$MODE" in
  install|update|repair) do_install; exit 0 ;;
  uninstall) do_uninstall; exit 0 ;;
esac

while true; do
  clear
  echo
  echo "  ========================================================"
  echo "    Fusion to Blender Lite  -  Installer"
  echo "  ========================================================"
  echo
  echo "    This sets up the bridge that brings your Fusion 360"
  echo "    models into Blender. It installs TWO parts:"
  echo
  echo "      [1] Fusion 360 add-in"
  echo "      [2] Blender add-on"
  echo
  echo "    BEFORE YOU START:"
  echo "      * Please CLOSE Fusion 360 and Blender first"
  echo "        (open files can block the copy)."
  echo
  echo "    Safe to run anytime: nothing else on your Mac is"
  echo "    changed, and Uninstall removes only these two parts."
  echo
  echo "  --------------------------------------------------------"
  echo "      [I]  Install"
  echo "      [U]  Update / Repair   (reinstall over existing)"
  echo "      [X]  Uninstall         (remove both parts)"
  echo "      [Q]  Quit"
  echo "  --------------------------------------------------------"
  echo
  read -r -p "   Choose (I/U/X/Q): " choice
  case "$choice" in
    [iI]) do_install ;;
    [uU]) do_install ;;
    [xX]) do_uninstall ;;
    [qQ]) echo; exit 0 ;;
    *) ;;
  esac
done
