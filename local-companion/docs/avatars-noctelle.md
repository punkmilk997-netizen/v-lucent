# Noctelle avatar assets (Sol → Noctelle)

Noctelle replaces Sol as the product identity. Avatar art from the Sol handoff is kept as **Noctelle-named** bundled media. The Sol PowerShell desktop runtime is **not** used or reinstalled.

## Bundled paths (`local-companion/public`)

| Asset | Path | Role |
|-------|------|------|
| Active (primary) | `media/noctelle/noctelle-active.png` | Full-size awake sprite (from `sol-active-v2.png`) |
| Active (alt) | `media/noctelle/noctelle-active-alt.png` | Earlier awake art (from `sol-active.png`) |
| Nap frames | `media/noctelle/noctelle-nap-0.png` … `nap-4.png` | Chibi nap cycle |
| Source sheet | `media/noctelle/noctelle-sprite-sheet.png` | Artist source sheet |
| Manifest | `media/noctelle/manifest.json` | Machine-readable defaults |
| VRM (existing) | `models/model1.vrm` | Default 3D avatar |
| Live2D-style | `models/aka.inx`, `models/Midori.inx` | PuppetRenderer models |

## Settings / UI

In the companion Settings → **Avatar**:

- **Presentation**: `VRM (3D)` or `Noctelle sprite (2D)`
- **Sprite**: choose active / alt / a nap frame (persisted as `avatar_mode` + `sprite_asset`)
- **Load VRM**: unchanged custom upload → `%APPDATA%/<app>/custom_vrms`

Defaults keep VRM mode so existing installs stay 3D; switch to sprite to use Sol-derived Noctelle art.

## What was not carried over

- No Sol `.ps1` / `.cmd` runtime
- No Sol AppData notes/doodles trial content
- No VRM in the Sol zip (sprites only)
