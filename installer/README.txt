============================================================
 Fusion to Blender Lite  -  Installer
============================================================

WHAT IS THIS?
  A one-step installer that sets up the bridge syncing your
  Fusion 360 models into Blender. It installs TWO parts:

    1) Fusion 360 add-in   (the server inside Fusion)
    2) Blender add-on       (the panel + Sync button)

HOW TO USE
  Windows:  double-click  install.bat
  macOS:    double-click  install.command
            (if blocked: right-click > Open)

  A small menu appears:
    [I] Install            - set up both parts
    [U] Update / Repair    - reinstall over an existing copy
    [X] Uninstall          - remove both parts
    [Q] Quit

BEFORE YOU START
  * Close Fusion 360 and Blender first (open files can block
    the copy). Run Update/Repair afterwards if anything failed.

WHERE THINGS GO (your user profile only - no admin needed)
  Windows
    Fusion:  %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\
    Blender: %APPDATA%\Blender Foundation\Blender\<ver>\scripts\addons\
  macOS
    Fusion:  ~/Library/Application Support/Autodesk/.../API/AddIns/
    Blender: ~/Library/Application Support/Blender/<ver>/scripts/addons/

  Nothing else on your computer is changed. Uninstall removes
  ONLY these two named folders.

AFTER INSTALLING
  1) Fusion 360: Utilities (or Tools) > Add-Ins >
     "Scripts and Add-Ins" > Add-Ins tab > select
     "fusion_to_blender_addon_fusion" > Run
  2) Blender: Edit > Preferences > Add-ons > enable
     "Fusion to Blender Lite", then restart Blender
  3) In Blender, just press Sync. The connection is automatic.

OPTIONAL: DIRECT STEP IMPORT
  The core sync above needs nothing extra. If you also want to
  open .step/.stp files directly in Blender (without Fusion),
  open the Fusion 360 panel in Blender and click
  "Install STEP Support" - it downloads the needed library.

NEED HELP?
  See the project page / README for troubleshooting.
============================================================
