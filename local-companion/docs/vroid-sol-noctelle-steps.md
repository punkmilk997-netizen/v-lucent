# VRoid Studio — Sol → Noctelle (manual step sheet)

**Why manual:** VRoid character creation is GUI-only. Per mouse rule, agents must not drive your cursor through VRoid. This sheet is the path to a true 3D Sol-like VRM.

## Already done (no action needed)

- Free **VRoid Studio 2.3.0** installed via winget at  
  `%LOCALAPPDATA%\Programs\VRoidStudio\2.3.0\VRoidStudio.exe`
- App is often already running (may be minimized). Title: `VRoid Studio 2.3.0 - Untitled*`
- Sol reference art: `local-companion/public/media/noctelle/noctelle-active.png`  
  (also `docs/sol-vroid-refs/sol-active-v2.png`)
- Interim bundled VRM (Sol likeness, cutout card — not sculpted):  
  `public/models/noctelle.vrm` → also copied to  
  `%APPDATA%\com.openclaw.companion\custom_vrms\Noctelle.vrm`

## Target look (from Sol art)

- Fem base, deep warm dark skin
- Long voluminous wavy black hair
- Glowing violet eyes
- Animal ears (black outside, lighter inside) + twin fluffy light tails
- Midnight purple/black gothic dress, sheer star mesh, platform boots
- Celestial silver/purple accents

Open the PNG beside VRoid while you work.

## Your clicks (about 20–40 minutes for a good first pass)

1. **Focus VRoid** (taskbar). If you see home/samples instead of editor: **Create New → Fem**.
2. If you already have **Untitled\*** in the Face editor with a default white-tee base, continue there (or File → New → Fem if you want a clean start).
3. **Face**
   - Darker skin (Body/skin color toward deep brown)
   - Large violet / purple irises; raise eye size slightly
   - Soften nose/mouth toward the Sol PNG
4. **Hairstyle**
   - Long black wavy preset closest to Sol; length past waist
   - Add volume / front strands; darken to near-black
5. **Accessories**
   - Animal ears (cat/fox-like); recolor to match Sol
   - Twin tails if available; fluff + light/cream tips
6. **Outfit**
   - Long dress / coat closest to gothic gown
   - Recolor to deep purple + black; reduce saturation on whites
   - Boots dark; stockings dark if present
   - Optional: custom textures later for star mesh (advanced)
7. **Look** — lighting check against the Sol PNG side-by-side
8. **Save project** (so Untitled\* is not lost):  
   `Documents\VRoid\Noctelle-Sol.vroid` (create folder if needed)
9. **Export VRM** (upload/export icon, top-right)
   - Name: `Noctelle`
   - Author: Punk Milk (or yours)
   - Save as:  
     `C:\Users\punkm\Desktop\desktop-assistant\v-lucent\local-companion\public\models\noctelle.vrm`  
     (overwrite the cutout)  
   - Also copy to:  
     `%APPDATA%\com.openclaw.companion\custom_vrms\Noctelle.vrm`
10. Tell the agent **"VRM exported"** — they will commit + push on `noctelle/stabilize-p0` without touching your mouse.

## Do not need

- Steam install of VRoid (standalone 2.3.0 is enough)
- Paying for Hub items for a first pass (use free presets)
- Letting any agent spam mouse control of the whole desktop

## Quality note

Until you export from VRoid, the best **Sol-likeness** VRM on disk is still the Blender **alpha-cutout card** baked from `noctelle-active.png`. The large Hub file `Desktop\desktop-assistant\Noctelle.vrm` (author Anna Lyra) is a full 3D humanoid but **not** Sol art — keep it as a 3D alternate only if you want that look.
