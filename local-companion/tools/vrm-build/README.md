# Noctelle / Sol billboard VRM builder

Produces `public/models/noctelle.vrm` from `public/media/noctelle/noctelle-active.png`
using Blender + [VRM Add-on for Blender](https://github.com/saturday06/VRM-Addon-for-Blender).

## Setup

1. Install Blender 4.2+ (tested: 5.2.1 LTS).
2. Download `VRM_Addon_for_Blender-*.zip` into this folder as `vrm_addon.zip`.
3. Run:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python tools\vrm-build\build_noctelle_vrm.py
```

## Quality

Paper-doll billboard (PNG plane on humanoid armature). Not AI mesh-from-image; that needs a GPU + TripoSR-class stack this machine lacked.
