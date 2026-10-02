"""Refine Noctelle-Sol toward sprite: dark skin, violet eyes, black hair, ears, gothic dress. Export VRM."""
import time, os, shutil
from pathlib import Path
import pyautogui, win32gui, win32con
import numpy as np
from PIL import Image

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1
AUTO = Path(r"C:\Users\punkm\Desktop\desktop-assistant\v-lucent\local-companion\docs\sol-vroid-refs\auto")
REPO = Path(r"C:\Users\punkm\Desktop\desktop-assistant\v-lucent\local-companion")
MODELS = REPO / "public" / "models"
APPDATA_VRM = Path(os.environ["APPDATA"]) / "com.openclaw.companion" / "custom_vrms"

TAB = {"face": 218, "hair": 372, "body": 528, "outfit": 665, "acc": 841, "look": 1020}
TAB_Y = 140
ICON_X = 115

# Target hex from Sol sprite (approx)
HEX_SKIN = "4A2C1F"
HEX_IRIS = "A855F7"  # glowing violet
HEX_HAIR = "12100F"  # near-black
HEX_OUTFIT_MAIN = "1A1028"  # midnight purple-black
HEX_OUTFIT_ACCENT = "6B21A8"
HEX_EAR = "1A1210"

def focus():
    found = []
    def enum(h, _):
        if "VRoid Studio" in win32gui.GetWindowText(h):
            found.append(h)
    win32gui.EnumWindows(enum, None)
    h = found[0]
    win32gui.ShowWindow(h, win32con.SW_MAXIMIZE)
    time.sleep(0.25)
    try:
        win32gui.SetForegroundWindow(h)
    except Exception:
        pass
    time.sleep(0.2)
    return win32gui.GetWindowRect(h), win32gui.GetWindowText(h)

def shot(n):
    p = AUTO / f"{n}.png"
    pyautogui.screenshot().save(p)
    print("SHOT", n)
    return p

def click(x, y, n=1):
    pyautogui.click(int(x), int(y), clicks=n)
    time.sleep(0.3)

def tab(name):
    click(TAB[name], TAB_Y)
    time.sleep(0.4)

def icon(y):
    click(ICON_X, y)
    time.sleep(0.35)

def zoom_out(n=14):
    pyautogui.moveTo(2200, 1100)
    for _ in range(n):
        pyautogui.scroll(-5)
        time.sleep(0.06)

def type_hex(hexcode):
    """Replace focused hex field."""
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.08)
    pyautogui.press("backspace")
    time.sleep(0.05)
    pyautogui.typewrite(hexcode, interval=0.03)
    time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(0.25)

def find_hex_fields(arr):
    """Find '#XXXXXX' like dark text near color UI - approximate by finding '#' pixels is hard.
    Instead find small saturated swatches and click to the RIGHT of them where hex often sits.
    """
    h, w = arr.shape[:2]
    # search left-mid panel for color chips: small high-sat rectangles
    x0, x1, y0, y1 = 180, 750, 240, 1500
    region = arr[y0:y1, x0:x1].astype(float)
    mx = region.max(2)
    mn = region.min(2)
    sat = np.where(mx > 20, (mx - mn) / np.maximum(mx, 1), 0)
    # Prefer mid-size blobs
    mask = sat > 0.35
    ys, xs = np.where(mask)
    if len(xs) < 10:
        return []
    # cluster
    clusters = []
    pts = list(zip(xs[::3] + x0, ys[::3] + y0))
    used = [False] * len(pts)
    for i, (x, y) in enumerate(pts):
        if used[i]:
            continue
        group = [(x, y)]
        used[i] = True
        for j, (x2, y2) in enumerate(pts):
            if not used[j] and abs(x2 - x) < 30 and abs(y2 - y) < 20:
                used[j] = True
                group.append((x2, y2))
        if 5 < len(group) < 400:
            cx = int(np.mean([p[0] for p in group]))
            cy = int(np.mean([p[1] for p in group]))
            # hex field typically ~80-180px right of swatch
            clusters.append((cx, cy, cx + 120, cy))
    # dedupe by y
    clusters.sort(key=lambda t: t[1])
    out = []
    for c in clusters:
        if not out or abs(c[1] - out[-1][1]) > 35:
            out.append(c)
    return out[:8]

def set_main_colors(hex_list):
    """For each found swatch row, click hex field and type."""
    arr = np.array(pyautogui.screenshot())
    fields = find_hex_fields(arr)
    print("color rows", fields)
    for i, hexcode in enumerate(hex_list):
        if i >= len(fields):
            break
        cx, cy, hx, hy = fields[i]
        # click hex text area
        click(hx, hy)
        time.sleep(0.2)
        type_hex(hexcode)
        # also click swatch then try picker corner for good measure
    return fields

def pick_thumb(col, row):
    x = 290 if col == 0 else 500
    y = 310 + row * 210
    click(x, y)
    time.sleep(0.45)

def scroll_grid(n=-6):
    pyautogui.moveTo(400, 650)
    pyautogui.scroll(n)
    time.sleep(0.3)

def find_export_icon():
    """Locate export icon in top-right content area (not window X)."""
    arr = np.array(pyautogui.screenshot())
    # From earlier screenshots: icons near top of viewport, right side, below title bar
    # Title bar ends ~y=110; icons around y=90-130 in content... actually content tabs at y=140
    # Export sits upper-right of 3D view - typically y~90-120 OR y~50-100 in app chrome under purple bar
    # Search for small icon buttons in region x=3000-3600, y=70-160
    region = arr[70:160, 2800:3600]
    # Dark icons on light/purple - look for compact dark blobs
    gray = region.mean(2)
    # Invert: icons darker
    dark = gray < 100
    # column sums
    # Just return candidate click points spaced
    candidates = []
    for x in range(3000, 3550, 35):
        for y in (95, 105, 115, 125):
            candidates.append((x, y))
    return candidates

def main():
    rect, title = focus()
    print("OPEN", title, rect)
    assert "Noctelle" in title or "Untitled" in title or "VRoid" in title
    shot("refine_start")
    zoom_out()
    shot("refine_zoom")

    # === HAIR long black ===
    tab("hair")
    icon(220)  # sets
    # Prefer long straight (row1 col0 earlier) then scroll for longer/wavier
    pick_thumb(0, 1)  # long straight
    shot("refine_hair1")
    for _ in range(5):
        scroll_grid(-7)
    # try lower thumbs for long wavy / ear hair
    for col, row in [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2), (0, 3), (1, 3)]:
        pick_thumb(col, row)
    shot("refine_hair2")

    # Color hair via right customize panel OR left - go Look? Better: click hair then color in right panel
    # Open Back hair for color controls
    icon(292)  # Front-ish
    time.sleep(0.3)
    set_main_colors([HEX_HAIR, HEX_HAIR])
    icon(364)  # Back
    time.sleep(0.3)
    set_main_colors([HEX_HAIR, "3A2A20"])
    icon(220)
    time.sleep(0.3)
    set_main_colors([HEX_HAIR, "2A1A14"])
    shot("refine_hair_color")

    # Extra ears
    icon(724)
    pick_thumb(1, 0)
    time.sleep(0.3)
    set_main_colors([HEX_EAR, "E8D5C4"])  # dark outside, light inside if 2 colors
    shot("refine_ears")

    # === FACE violet eyes + darker if skin here ===
    tab("face")
    icon(346)  # Irises
    time.sleep(0.4)
    set_main_colors([HEX_IRIS, "D8B4FE", "FFFFFF"])
    shot("refine_iris")

    # Eyes sets - larger
    icon(281)
    pick_thumb(1, 1)
    pick_thumb(0, 2)
    shot("refine_eyes")

    # === BODY skin ===
    tab("body")
    icon(220)
    time.sleep(0.5)
    shot("refine_body_panel")
    # Body panel often has skin color at top of right or left
    fields = set_main_colors([HEX_SKIN, "3D2418", "2A1810"])
    # Also try clicking known body swatch positions from earlier (246,562)
    for xy, hx in [((246, 562), HEX_SKIN), ((411, 561), "5C3A28"), ((350, 400), HEX_SKIN)]:
        click(*xy)
        time.sleep(0.25)
        type_hex(hx)
    shot("refine_skin")

    # Face paint / lips area - try skin under face by scrolling icons
    tab("face")
    pyautogui.moveTo(ICON_X, 800)
    for _ in range(12):
        pyautogui.scroll(-5)
        time.sleep(0.08)
    for y in range(900, 1350, 50):
        icon(y)
        arr = np.array(pyautogui.screenshot())
        hdr = arr[185:240, 170:520]
        Image.fromarray(hdr).save(AUTO / f"refine_hdr_{y}.png")
        # If header suggests Skin, set color
        fields = find_hex_fields(arr)
        if fields and y > 1000:
            set_main_colors([HEX_SKIN, "5C3A28"])
            shot(f"refine_maybe_skin_{y}")
    shot("refine_after_face_scroll")

    # === OUTFIT gothic ===
    tab("outfit")
    icon(220)  # whole sets
    # Seek black dress - scroll and pick dark outfits
    for page in range(4):
        for col, row in [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)]:
            pick_thumb(col, row)
            time.sleep(0.15)
        scroll_grid(-8)
    shot("refine_outfit_pick")
    # One-piece
    icon(436)
    for page in range(3):
        for col, row in [(0, 0), (1, 0), (0, 1), (1, 1)]:
            pick_thumb(col, row)
        scroll_grid(-8)
    shot("refine_onepiece")
    # Recolor current outfit
    icon(220)
    time.sleep(0.4)
    set_main_colors([HEX_OUTFIT_MAIN, HEX_OUTFIT_ACCENT, "0A0A0A", "C4B5FD"])
    # Tops/bottoms colors
    for iy in (292, 364, 508, 796, 868):
        icon(iy)
        time.sleep(0.25)
        set_main_colors([HEX_OUTFIT_MAIN, "0A0A0A", HEX_OUTFIT_ACCENT])
    shot("refine_outfit_color")

    zoom_out(8)
    tab("look")
    shot("refine_look")

    # Save
    pyautogui.hotkey("ctrl", "s")
    time.sleep(1.5)
    shot("refine_saved")

    # === EXPORT ===
    # Click export icon carefully - from Look view top-right content icons
    # Window close is at ~ right edge y~20; export is LOWER in content ~ y=100 area but LEFT of window controls
    rect, _ = focus()
    # Content export icons: typically around x = right - 250 to right - 120, y ~ 95-130
    # Avoid x > right-80 (window buttons)
    right = rect[2]
    # Use DPI-aware: pyautogui screen is 3840 wide; window roughly full
    export_candidates = [
        (3400, 100), (3350, 100), (3300, 100), (3250, 100), (3200, 105),
        (3450, 110), (3380, 115), (3320, 120), (3280, 90), (3500, 100),
    ]
    exported = False
    for x, y in export_candidates:
        if x > 3700:  # steer clear of close
            continue
        click(x, y)
        time.sleep(0.7)
        arr = np.array(pyautogui.screenshot())
        # Detect modal: center becomes more white dialog
        c = arr[500:1600, 900:2900]
        # Or detect new UI with form fields
        shot(f"extry_{x}_{y}")
        # Check for "Export" by looking if previous look panel disappeared / overlay
        # Simple: if many more white pixels in center mid band
        if c.mean() > 220 and c.std() < 50:
            print("likely blank still")
            continue
        # Look for purple/blue buttons typical of VRoid dialogs
        blue = ((c[:,:,2] > 150) & (c[:,:,0] < 120)).sum()
        if blue > 500 or c.std() > 40:
            print("dialog candidate", x, y, "blue", int(blue), "std", float(c.std()))
            exported = True
            break
    shot("export_ui")

    if exported:
        # Fill name Noctelle, author Punk Milk
        # Click through form - name field often near top of dialog
        time.sleep(0.5)
        # Try tab through fields
        for _ in range(3):
            pyautogui.press("tab")
            time.sleep(0.15)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.typewrite("Noctelle", interval=0.04)
        pyautogui.press("tab")
        time.sleep(0.15)
        pyautogui.typewrite("Punk Milk", interval=0.04)
        shot("export_form")
        # Click export/save button - usually bottom right of dialog blue button
        # Try several
        for xy in [(2400, 1600), (2500, 1650), (2300, 1550), (2200, 1700), (2600, 1580)]:
            click(*xy)
            time.sleep(0.8)
            shot(f"export_btn_{xy[0]}")
        # Save file dialog
        time.sleep(1)
        target = str(MODELS / "noctelle.vrm")
        # Focus filename box Ctrl+L sometimes in explorer
        pyautogui.hotkey("alt", "n")  # filename field common
        time.sleep(0.3)
        pyautogui.typewrite(target, interval=0.015)
        time.sleep(0.4)
        pyautogui.press("enter")
        time.sleep(2)
        # Confirm overwrite Yes
        pyautogui.press("y")
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(5)
        shot("export_done")
    else:
        print("EXPORT_ICON_NOT_FOUND - will try menu")
        # Hamburger / three-dot
        click(3550, 100)
        time.sleep(0.5)
        shot("kebab_menu")

    print("PHASE_REFINE_DONE")
    # Report whether vrm updated
    vrm = MODELS / "noctelle.vrm"
    if vrm.exists():
        print("VRM_MTIME", time.ctime(vrm.stat().st_mtime), "SIZE", vrm.stat().st_size)

if __name__ == "__main__":
    main()
