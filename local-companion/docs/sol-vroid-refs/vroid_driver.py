"""VRoid Studio click helper for Sol/Noctelle. Uses pyautogui logical coords (DPI-aware)."""
import time, sys, os
from pathlib import Path
import pyautogui
import ctypes
from ctypes import wintypes

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.15

OUT = Path(r"C:\Users\punkm\Desktop\desktop-assistant\v-lucent\local-companion\docs\sol-vroid-refs\auto")
OUT.mkdir(exist_ok=True)

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

def vroid_hwnd():
    import win32gui
    found = []
    def enum(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if "VRoid Studio" in title:
            found.append((hwnd, title))
    win32gui.EnumWindows(enum, None)
    return found[0] if found else (None, None)

def focus_vroid():
    try:
        import win32gui, win32con
        hwnd, title = vroid_hwnd()
        if not hwnd:
            print("NO_VROID")
            return None
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        print(f"FOCUSED {title} rect=({r.left},{r.top},{r.right},{r.bottom})")
        return r
    except Exception as e:
        # fallback without pywin32
        print("focus fallback", e)
        return None

def shot(name):
    path = OUT / f"{name}.png"
    im = pyautogui.screenshot()
    im.save(path)
    print(f"SHOT {path} {im.size}")
    return path

def click(x, y, clicks=1):
    print(f"CLICK {x},{y} x{clicks}")
    pyautogui.click(x, y, clicks=clicks)
    time.sleep(0.35)

def rel(r, fx, fy):
    """Click fraction of window width/height."""
    w = r.right - r.left
    h = r.bottom - r.top
    x = int(r.left + w * fx)
    y = int(r.top + h * fy)
    click(x, y)
    return x, y

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shot"
    r = focus_vroid()
    if cmd == "shot":
        shot(sys.argv[2] if len(sys.argv) > 2 else "now")
    elif cmd == "click":
        click(int(sys.argv[2]), int(sys.argv[3]))
        shot(sys.argv[4] if len(sys.argv) > 4 else "after")
    elif cmd == "rel":
        if r is None:
            # assume fullscreen primary
            class R: pass
            r = R(); r.left=0; r.top=0; r.right=3840; r.bottom=2160
        rel(r, float(sys.argv[2]), float(sys.argv[3]))
        shot(sys.argv[4] if len(sys.argv) > 4 else "after")
    elif cmd == "info":
        print("screen", pyautogui.size(), "pos", pyautogui.position())
        shot("info")
