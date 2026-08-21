"""What a macOS buyer gets when they unzip the download.

None of this can be checked from Blender or from Fusion, and none of it is
visible on Windows -- which is exactly why it broke. Three separate times the
mac half shipped wrong while every other suite stayed green:

  * install.command carried CRLF, so its shebang ended in a carriage return
    and macOS answered "bad interpreter"
  * the paid bundle's install.command had no executable bit at all, so a
    double-click did nothing (and even the free one declared its 0o755 under
    host-OS 0/MS-DOS, where unzip drops the mode on the way out)
  * install.command drifted behind install.bat: the .bat branches on the paid
    bundle in five places, the .command in two, so a buyer was told to enable
    an add-on called "Lite" that their download does not contain

So the bundles are opened here and inspected as bytes. The end-to-end run --
really executing install.command against a throwaway HOME -- lives in
tests/check_bundles.sh, because it needs a shell; these are the checks that
must hold everywhere and cost nothing.
"""
import os
import zipfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
FREE = os.path.abspath(os.path.join(HERE, ".."))
PRO = os.path.abspath(os.path.join(FREE, "..", "bridge-pro"))

BUNDLES = [
    os.path.join(FREE, "fusion_to_blender_bridge_installer.zip"),
    os.path.join(FREE, "fusion_to_blender_addon_fusion.zip"),
    os.path.join(PRO, "bridge_pro_installer.zip"),
]

# Files that belong to whoever built the add-on, not to whoever bought it. The
# paid bundle was shipping .vscode into the buyer's Fusion AddIns folder.
CRUFT = (".vscode", ".idea", ".DS_Store", "Thumbs.db", ".git", "__pycache__")

# The single entry point is the installer at the bundle root. A second copy
# inside an add-on folder rides along into Fusion's AddIns folder.
INSTALLER_NAMES = {"install.bat", "install.command", "install.sh"}


def _bundles():
    found = [b for b in BUNDLES if os.path.exists(b)]
    if not found:
        pytest.skip("no bundles built yet -- run build_installer.py")
    return found


@pytest.mark.parametrize("bundle", _bundles(), ids=os.path.basename)
def test_mac_installer_is_executable(bundle):
    """A .command without the executable bit does nothing when double-clicked.

    create_system is asserted too, and is the half that is easy to miss: unzip
    reads permissions out of the high bits only when the host-OS byte says Unix
    (3). zipfile defaults it to 0 on Windows, and then a perfectly correct
    0o755 is thrown away as the buyer extracts.
    """
    with zipfile.ZipFile(bundle) as zf:
        scripts = [i for i in zf.infolist() if i.filename.endswith((".command", ".sh"))]
        assert scripts, f"{os.path.basename(bundle)} ships no macOS installer"
        for info in scripts:
            mode = (info.external_attr >> 16) & 0xFFFF
            assert mode & 0o111, f"{info.filename}: mode {oct(mode)} is not executable"
            assert info.create_system == 3, (
                f"{info.filename}: host OS {info.create_system}, so unzip will "
                f"drop mode {oct(mode)}"
            )


@pytest.mark.parametrize("bundle", _bundles(), ids=os.path.basename)
def test_line_endings_match_the_platform(bundle):
    """CRLF in a shebang is what "bad interpreter" on macOS actually is."""
    with zipfile.ZipFile(bundle) as zf:
        for info in zf.infolist():
            data = zf.read(info.filename)
            if info.filename.endswith((".command", ".sh")):
                assert b"\r\n" not in data, f"{info.filename} carries CRLF"
                assert data.startswith(b"#!"), f"{info.filename} lost its shebang"
            elif info.filename.endswith(".bat"):
                assert data.count(b"\r\n") == data.count(b"\n"), (
                    f"{info.filename} has bare LF; cmd.exe mis-parses it"
                )


@pytest.mark.parametrize("bundle", _bundles(), ids=os.path.basename)
def test_no_developer_cruft(bundle):
    with zipfile.ZipFile(bundle) as zf:
        for name in zf.namelist():
            parts = name.split("/")
            bad = [p for p in parts if p in CRUFT]
            assert not bad, f"{name} ships {bad[0]}"


@pytest.mark.parametrize("bundle", _bundles(), ids=os.path.basename)
def test_installer_scripts_only_at_the_root(bundle):
    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        # Depth 1 (top/install.command) is the entry point; deeper is a stowaway.
        stray = [n for n in names
                 if n.rsplit("/", 1)[-1] in INSTALLER_NAMES and n.count("/") > 1]
        # ...unless the bundle IS a single add-on folder, which carries its own.
        if any(n.count("/") == 1 and n.rsplit("/", 1)[-1] in INSTALLER_NAMES
               for n in names):
            assert not stray, f"installer scripts buried in add-on folders: {stray}"


def test_paid_installer_names_the_paid_addon():
    """The buyer is told which add-on to enable, and it must be theirs.

    install.bat branches on the paid bundle in five places. install.command
    had two of them, so macOS buyers were sent looking for "Fusion to Blender
    Lite" in their add-on list -- a name their download does not contain.
    """
    bundle = os.path.join(PRO, "bridge_pro_installer.zip")
    if not os.path.exists(bundle):
        pytest.skip("paid bundle not built")
    with zipfile.ZipFile(bundle) as zf:
        top = zf.namelist()[0].split("/")[0]
        for script in (f"{top}/install.command", f"{top}/install.bat"):
            text = zf.read(script).decode("utf-8", "replace")
            assert "Fusion to Blender Bridge" in text, (
                f"{script} never names the add-on the buyer actually has"
            )
            # HAS_PRO decides which name is printed, so the free string may
            # still be in the file -- but it must be inside a branch.
            assert ("HAS_PRO" in text) or ("Lite" not in text), (
                f"{script} says Lite with no paid branch guarding it"
            )
