# Noctelle / Sol cutout-card VRM builder

Produces `public/models/noctelle.vrm` from `public/media/noctelle/noctelle-active.png`
using Blender + [VRM Add-on for Blender](https://github.com/saturday06/VRM-Addon-for-Blender).

## Setup

1. Install Blender 4.2+ (tested: 5.2.1 LTS).
2. VRM Add-on already under `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\VRM_Addon_for_Blender-release`
   (optional zip at `tools/vrm-build/vrm_addon.zip` for reinstall).
3. Run:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python tools\vrm-build\build_noctelle_vrm.py
```

## Quality

Alpha-cutout shallow card: PNG silhouette mesh with thickness + height-banded bone weights.
Better than a flat rectangular billboard; still not AI mesh-from-image (this PC has AMD GPU, no torch/TripoSR).
