# Privacy Policy — Fusion to Blender Bridge

**This software collects no data.** Nothing is sent to us or to anyone else.

This policy covers Fusion to Blender Bridge in all its forms: the Fusion 360
add-in, the Blender add-on (free and paid builds), and the installer that sets
them up.

## 1. What data the app collects

None.

The software does not collect, transmit, store or share any information about
you, your computer, your Autodesk account, or the documents you open. It
contains no analytics, no crash reporting, no usage tracking, no account
system and no licence check.

## 2. How data is handled and used

No data is collected, so there is nothing to describe under collection. For
transparency, here is everything the software touches:

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
- The Fusion add-in writes a **diagnostic log** to a text file on your own
  machine — see section 4, which says exactly what is in it and how to remove
  it.

## 3. Third parties

**No data is shared with any third party, so there is no third party that
would need to provide equivalent protection.** There are no analytics
providers, advertising networks, third-party SDKs, or affiliated companies
(parent, subsidiary or related entity) receiving anything from this software.
There is no back end: we operate no server that this software talks to.

One honest qualification. If — and only if — you press the button that
installs STEP support, your computer makes an HTTPS request to PyPI to
download the `cadquery-ocp` package. As with every request any computer makes
to any website, **PyPI sees the IP address the request came from.** Nothing
about you, your account or your documents is sent; it is the same anonymous
package request that any `pip install` produces, and what PyPI does with its
own server logs is governed by the Python Software Foundation's privacy
policy, not by us. If you would rather not make that request, do not press
that button — every other feature works without it.

## 4. Retention — what is kept, where, and for how long

We keep nothing, because we receive nothing. Everything below stays on your
own machine until you delete it.

| What | Where (Windows) | Kept for |
|---|---|---|
| Blender add-on settings (language, auto-connect) | Blender's own preferences: `%APPDATA%\Blender Foundation\Blender\<version>\config\userpref.blend` | Until you change or remove them |
| Per-scene options (quality, toggles) | Inside the `.blend` file you save | As long as you keep that file |
| Fusion add-in files and settings | `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\fusion_to_blender_addon_fusion\` | Until uninstalled |
| **Diagnostic log** | `%USERPROFILE%\Documents\fusion_bridge_log.txt` | **Appended to on every sync, never rotated or deleted by us** |
| STEP support packages, if you installed them | Your Python user directory, e.g. `%APPDATA%\Python\Python311\site-packages` | Until you uninstall them |

**About the diagnostic log.** It records what the add-in did during a sync:
body and component names, appearance names, counts, and errors. Those names
come from your design, so treat the file as you would the design itself. It is
written only to your own disk and is never transmitted anywhere. It exists so
that when a sync goes wrong you have evidence instead of a guess. You can
delete it at any time — the add-in simply starts a new one — and you can send
it to us voluntarily when reporting a problem, which is the only circumstance
in which we would ever see it.

## 5. Deleting your data, and withdrawing consent

**There is no collection consent to withdraw,** because nothing is collected
and nothing is switched on that would collect it.

The one action that asks for your consent is the STEP-support install. It does
nothing until you press its button. To undo it, uninstall the downloaded
packages with `pip uninstall cadquery-ocp vtk` — the rest of the software is
unaffected.

**To remove everything this software has put on your machine:**

1. Run the installer again and choose Uninstall (or remove the add-on from
   Blender's Preferences, and the add-in folder from Fusion's AddIns folder).
2. Delete the diagnostic log at `%USERPROFILE%\Documents\fusion_bridge_log.txt`.
3. Delete the STEP packages, if you installed them (step above).

Blender's own preference file and your `.blend` files belong to Blender and to
you; removing the add-on leaves them intact.

**Requests.** You may still write to <inspace9018@gmail.com> to ask what we
hold about you, or to ask for deletion. Because we hold nothing, the honest
answer will be that there is nothing to disclose or erase — and we will say so
in writing **within 30 days** of your request.

## Verifiability

The complete source code is published under GPL-3.0-or-later at
<https://github.com/inspace9018/fusion-to-blender-bridge>, so every claim
above can be checked by reading the code.

## Contact

Questions about this policy: <inspace9018@gmail.com>

Publisher: Nexus Lab
Last updated: 2026-08-26
