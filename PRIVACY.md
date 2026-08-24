# Privacy Policy — Fusion to Blender Bridge

**This software collects no data.**

This policy covers Fusion to Blender Bridge in all its forms: the Fusion 360
add-in, the Blender add-on (free and paid builds), and the installer that sets
them up.

## 1. What data the app collects

None.

The software does not collect, transmit, store or share any information about
you, your computer, your Autodesk account, or the documents you open. It
contains no analytics, no crash reporting, no usage tracking, no account
system and no licence check.

## 2. How data is collected and used

Not applicable — no data is collected.

For transparency, here is everything the software touches:

- The Fusion 360 add-in reads the design document you have open — body
  geometry, component structure, transforms, visibility, appearance names with
  their colour and finish properties, and joint definitions. It reads only
  when Blender asks, and it never writes to your document.
- That data travels over a local socket on `127.0.0.1` to Blender running on
  the **same computer**, where it becomes your Blender scene. It is not sent
  anywhere else, and the bridge itself makes no outbound network connections.
- One optional feature reaches the internet: the STEP-support installer, which
  -- only when you press its button -- downloads the third-party `cadquery-ocp`
  package from PyPI (pypi.org / files.pythonhosted.org) using pip. No data
  about you or your documents is sent; it is a package download, TLS
  verification is never bypassed, and nothing runs without your click.
- Settings you choose (language, port, quality) are stored locally on your own
  machine, inside Fusion's and Blender's own configuration storage.

## 3. Third parties

No data is shared with any third party, because no data is collected. There
are no third-party services, SDKs, analytics providers or advertising networks
in the software.

The optional STEP-support installer fetches one third-party software package,
`cadquery-ocp`, from PyPI. That is code coming in, not data going out: PyPI
receives the same anonymous package request any `pip install` produces, and
nothing about you or your documents.

## Verifiability

The complete source code is published under GPL-3.0-or-later at
<https://github.com/inspace9018/fusion-to-blender-bridge>, so every claim
above can be checked by reading the code.

## Contact

Questions about this policy: <inspace9018@gmail.com>

Publisher: Nexus Lab
Last updated: 2026-08-25
