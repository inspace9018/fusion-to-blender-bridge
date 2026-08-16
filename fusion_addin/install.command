#!/bin/bash
# Fusion to Blender Bridge - macOS one-click installer.
# Double-click this file (or: right-click > Open) to copy the add-in into
# Fusion 360's AddIns folder. If macOS blocks it, run once in Terminal:
#     chmod +x install.command

SRC="$(cd "$(dirname "$0")" && pwd)"
ADDIN_NAME="$(basename "$SRC")"
ADDINS="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
DEST="$ADDINS/$ADDIN_NAME"

echo
echo "  Fusion to Blender Bridge - one-click installer"
echo "  ----------------------------------------------"
echo "  Copying the add-in into Fusion 360's AddIns folder:"
echo "    From: $SRC"
echo "    To:   $DEST"
echo

mkdir -p "$DEST"
if ! cp -R "$SRC/." "$DEST/"; then
    echo "  [!] Copy failed. If Fusion 360 is open, close it (or Stop the add-in) and try again."
    echo
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

echo "  [OK] Installed."
echo
echo "  Next steps in Fusion 360:"
echo "    1) Open Fusion 360"
echo "    2) Utilities (or Tools) > Add-Ins > \"Scripts and Add-Ins\""
echo "    3) Open the Add-Ins tab, select \"$ADDIN_NAME\", click Run"
echo
echo "  The bridge server then starts automatically. In Blender, just press Sync."
echo
read -n 1 -s -r -p "Press any key to close..."
