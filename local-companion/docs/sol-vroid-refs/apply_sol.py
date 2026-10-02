"""Apply Sol look in VRoid Studio 2.3 from noctelle sprite refs, then save+export."""
import time, os, shutil
from pathlib import Path
import pyautogui
import win32gui, win32con
from PIL import Image
import numpy as np

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.12
AUTO = Path(r"C:\Users\punkm\Desktop\desktop-assistant\v-lucent\local-companion\docs\sol-vroid-refs\auto")
AUTO.mkdir(exist_ok=True)
REPO = Path(r"C:\Users\punkm\Desktop\desktop-assistant\v-lucent\local-companion")
MODELS = REPO / "public" / "models"
APPDATA_VRM = Path(os.environ["APPDATA"]) / "com.openclaw.companion" / "custom_vrms"
DOCS_VROID = Path(os.environ["USERPROFILE"]) / "Documents" / "VRoid"
DOCS_VROID.mkdir(parents=True, exist_ok=True)

# Top tabs (logical/DPI coords)
TAB = {"face": 218, "hair": 372, "body": 528, "outfit": 665, "acc": 841, "look": 1020}
TAB_Y = 140
ICON_X = 115

def focus():
    found = []
    def enum(h, _):
        if "VRoid Studio" in win32gui.GetWindowText(h):
            found.append(h)
    win32gui.EnumWindows(enum, None)
    if not found:
        raise RuntimeError("VRoid not found")
    h = found[0]
    win32gui.ShowWindow(h, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(h)
    except Exception:
        pass
    time.sleep(0.35)
    return win32gui.GetWindowRect(h)

def shot(name):
    p = AUTO / f"{name}.png"
    pyautogui.screenshot().save(p)
    print("SHOT", name)
    return p

def click(x, y, n=1):
    pyautogui.click(x, y, clicks=n)
    time.sleep(0.35)

def tab(name):
    click(TAB[name], TAB_Y)
    time.sleep(0.45)

def icon(y):
    click(ICON_X, y)
    time.sleep(0.4)

def scroll_panel(clicks=-6):
    # hover over preset grid and scroll
    pyautogui.moveTo(400, 600)
    time.sleep(0.1)
    pyautogui.scroll(clicks)
    time.sleep(0.35)

def pick_thumb(col, row):
    """2-col preset grid approx centers in panel."""
    # calibrated roughly for current window
    x = 280 if col == 0 else 480
    y = 300 + row * 200
    click(x, y)
    time.sleep(0.5)

def find_color_swatches(im_arr, x0=170, x1=700, y0=240, y1=1400):
    """Find saturated rectangular color chips."""
    region = im_arr[y0:y1, x0:x1].astype(float)
    mx = region.max(axis=2)
    mn = region.min(axis=2)
    sat = np.where(mx > 30, (mx - mn) / np.maximum(mx, 1), 0)
    # also not near-white
    mask = (sat > 0.25) & (mx < 250)
    # find blobs via simple downsample
    ys, xs = np.where(mask)
    if len(xs) < 20:
        return []
    pts = list(zip(xs + x0, ys + y0))
    # cluster greedily
    clusters = []
    used = set()
    for i, (x, y) in enumerate(pts[::5]):
        if i in used:
            continue
        group = [(x, y)]
        for j, (x2, y2) in enumerate(pts[::5]):
            if abs(x2 - x) < 25 and abs(y2 - y) < 25:
                group.append((x2, y2))
                used.add(j)
        if len(group) > 8:
            cx = int(np.mean([p[0] for p in group]))
            cy = int(np.mean([p[1] for p in group]))
            clusters.append((cx, cy))
    return clusters[:12]

def set_hsv_color(target_rgb, swatch_xy=None):
    """Click a color swatch then pick approximate color in picker."""
    if swatch_xy:
        click(*swatch_xy)
        time.sleep(0.6)
    im = np.array(pyautogui.screenshot())
    # Look for large color picker (HSV square) - high local variance region
    # Heuristic: find saturated area that looks like a square picker (~180-280px)
    h, w = im.shape[:2]
    best = None
    best_score = 0
    for y in range(200, 1400, 20):
        for x in range(200, 1600, 20):
            patch = im[y:y+40, x:x+40].astype(float)
            if patch.size < 100:
                continue
            sat = (patch.max(axis=2) - patch.min(axis=2)).mean()
            if sat > best_score:
                best_score = sat
                best = (x + 20, y + 20)
    if best and best_score > 40:
        # Map target into picker: click relative position by hue/value guess
        r, g, b = target_rgb
        # crude: darker colors toward bottom-left of SV square; hue on bar
        # First click SV area toward desired lightness
        lum = (r + g + b) / 3
        # Prefer purple: high B relative, medium
        click(best[0] + int((b - 128) / 8), best[1] + int((200 - lum) / 4))
        time.sleep(0.3)
        # Try hue bar to the right of SV square
        click(best[0] + 160, best[1] - 40 + int((1 - b / 255) * 120))
        time.sleep(0.3)
        # Click again in SV for darkness
        sx = best[0] - 40 + int((max(r, g, b) / 255) * 80)
        sy = best[1] - 40 + int((1 - lum / 255) * 100)
        click(sx, sy)
        time.sleep(0.3)
        # Confirm by clicking elsewhere / Enter
        pyautogui.press("enter")
        time.sleep(0.2)
        return True
    print("No color picker found, score", best_score)
    return False

def zoom_out():
    # Move to viewport center-right and scroll out
    pyautogui.moveTo(2200, 1100)
    for _ in range(12):
        pyautogui.scroll(-4)
        time.sleep(0.08)
    time.sleep(0.3)

def main():
    focus()
    shot("sol_start")
    zoom_out()
    shot("sol_zoomed")

    # --- HAIR: long style + ears ---
    tab("hair")
    icon(220)  # Hairstyle Sets
    # scroll to find long / animal ear sets
    for _ in range(3):
        scroll_panel(-5)
    # click likely long hair thumbs (try several)
    for col, row in [(0, 1), (0, 2), (1, 2), (0, 3), (1, 0)]:
        pick_thumb(col, row)
    shot("sol_hair_sets")
    # scroll more for animal-ear hairstyle set
    for _ in range(4):
        scroll_panel(-5)
    pick_thumb(0, 3)  # animal ears style from earlier describe
    pick_thumb(1, 3)
    shot("sol_hair_sets2")

    # Extra (animal ears) ~724
    icon(724)
    time.sleep(0.3)
    pick_thumb(1, 0)  # pointed ears
    pick_thumb(0, 1)
    shot("sol_ears")

    # Hair color - open Back Hair or Sets color if visible
    icon(220)
    time.sleep(0.3)
    im = np.array(pyautogui.screenshot())
    swatches = find_color_swatches(im)
    print("hair swatches", swatches)
    if swatches:
        set_hsv_color((15, 10, 12), swatches[0])  # near black
    shot("sol_hair_color")

    # --- FACE: iris violet, larger eyes ---
    tab("face")
    icon(346)  # Irises
    time.sleep(0.4)
    im = np.array(pyautogui.screenshot())
    swatches = find_color_swatches(im)
    print("iris swatches", swatches)
    if swatches:
        set_hsv_color((140, 40, 220), swatches[0])  # violet
    else:
        # click typical color chip area
        click(350, 320)
        time.sleep(0.5)
        set_hsv_color((140, 40, 220), None)
    shot("sol_iris")

    # Face sets - pick larger eye preset (row1 col1 often moe)
    icon(215)
    pick_thumb(1, 1)
    pick_thumb(0, 1)
    shot("sol_faceset")

    # --- BODY: skin ---
    tab("body")
    icon(220)
    time.sleep(0.4)
    im = np.array(pyautogui.screenshot())
    # save body panel crop
    Image.fromarray(im).crop((160, 180, 750, 1400)).save(AUTO / "sol_body_panel.png")
    swatches = find_color_swatches(im)
    print("body swatches", swatches)
    # Also try Face Skin by scrolling face icons - Face Paint was at 1280, Skin may be near cheeks
    if swatches:
        # pick darkest-looking warm brown
        set_hsv_color((70, 40, 28), swatches[0])
    shot("sol_body")

    # Try Face > scroll to Skin (between lips and face paint or after)
    tab("face")
    # scroll icon rail down
    pyautogui.moveTo(ICON_X, 700)
    for _ in range(10):
        pyautogui.scroll(-4)
        time.sleep(0.1)
    for y in [1000, 1050, 1100, 1150, 1200, 1250]:
        icon(y)
        im = np.array(pyautogui.screenshot())
        hdr = im[185:235, 170:550]
        Image.fromarray(hdr).save(AUTO / f"sol_face_hdr_{y}.png")
        swatches = find_color_swatches(im)
        # if we see skin-like peach swatches, recolor
        if swatches and y >= 1100:
            set_hsv_color((72, 42, 30), swatches[0])
            shot(f"sol_skin_{y}")
            break
    shot("sol_skin_final")

    # --- OUTFIT: black dress then recolor purple ---
    tab("outfit")
    icon(220)  # Whole Sets
    for _ in range(2):
        scroll_panel(-5)
    # black dress was ~item 8 in earlier list - try several
    for col, row in [(1, 2), (0, 3), (1, 3), (0, 2), (1, 1)]:
        pick_thumb(col, row)
    shot("sol_outfit1")
    for _ in range(3):
        scroll_panel(-5)
    for col, row in [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)]:
        pick_thumb(col, row)
    shot("sol_outfit2")

    # One-piece category ~364 from outfit sweep (Bottoms was 335, so one-piece later)
    icon(436)  # guess one-piece / tops area
    time.sleep(0.3)
    for col, row in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        pick_thumb(col, row)
    shot("sol_onepiece")

    # Recolor outfit - find color chips
    icon(220)
    time.sleep(0.3)
    im = np.array(pyautogui.screenshot())
    swatches = find_color_swatches(im)
    print("outfit swatches", swatches)
    for i, sw in enumerate(swatches[:3]):
        set_hsv_color((40, 20, 70) if i == 0 else (60, 30, 100), sw)  # deep purple/black
    shot("sol_outfit_color")

    # Shoes dark
    icon(868)  # shoes from outfit sweep
    time.sleep(0.3)
    for col, row in [(0, 0), (1, 0), (0, 1)]:
        pick_thumb(col, row)
    shot("sol_shoes")

    # --- ACCESSORIES: add if empty ---
    tab("acc")
    time.sleep(0.4)
    # Click "Add an Accessory" button - large gray button ~ center of left panel
    click(420, 320)
    time.sleep(0.8)
    shot("sol_acc_add")
    # If modal opened, try pick ears/tails
    for col, row in [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2)]:
        pick_thumb(col, row)
    pyautogui.press("escape")
    time.sleep(0.3)
    shot("sol_acc")

    zoom_out()
    tab("look")
    shot("sol_look")

    # --- SAVE PROJECT ---
    tab("face")  # ensure editor
    pyautogui.hotkey("ctrl", "s")
    time.sleep(1.2)
    shot("sol_save_dlg")
    # Type path if save dialog
    save_path = str(DOCS_VROID / "Noctelle-Sol.vroid")
    # Also try repo path
    repo_save = str(REPO / "assets" / "vroid" / "Noctelle-Sol.vroid")
    Path(repo_save).parent.mkdir(parents=True, exist_ok=True)
    # If dialog: type name
    pyautogui.typewrite("Noctelle-Sol", interval=0.05)
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.5)
    shot("sol_saved")

    # --- EXPORT VRM ---
    # Top-right export/upload icon - typically near window controls
    # Try common positions + menu
    for xy in [(3180, 100), (3100, 100), (3000, 100), (2900, 100), (2800, 95), (2700, 95)]:
        click(*xy)
        time.sleep(0.6)
        shot(f"sol_export_try_{xy[0]}")
        im = np.array(pyautogui.screenshot())
        # detect dialog by darker overlay or "Export" text area
        # If we see a modal, break
        # Check for large white dialog center
        center = im[700:1400, 1200:2600]
        if center.mean() > 200 and center.std() > 25:
            print("Possible dialog at", xy)
            break
    # Also try Alt path via hamburger menu File
    click(100, 140)  # hamburger near tabs
    time.sleep(0.5)
    shot("sol_menu")
    # Try keyboard shortcuts common in VRoid - none reliable
    # Click through top-right icons systematically
    r = focus()
    # icons usually just left of minimize
    for dx in range(80, 500, 40):
        x = r[2] - dx
        y = r[1] + 40
        if y < 20:
            y = 90
        click(x, y)
        time.sleep(0.45)
        im = pyautogui.screenshot()
        arr = np.array(im)
        # modal-ish: check variance in center
        c = arr[600:1500, 1000:2800]
        if c.mean() > 210 and (c.std() > 30):
            im.save(AUTO / f"sol_modal_{dx}.png")
            print("modal candidate dx", dx)
            break
    shot("sol_export_state")

    print("SAVE_PATH", save_path)
    print("REPO_SAVE", repo_save)
    print("DONE_PHASE_EDIT")

if __name__ == "__main__":
    main()
