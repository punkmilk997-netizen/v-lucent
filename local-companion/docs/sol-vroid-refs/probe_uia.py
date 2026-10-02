from pywinauto import Desktop
wins = Desktop(backend="uia").windows()
for w in wins:
    t = w.window_text()
    if t and ("VRoid" in t or "Untitled" in t):
        print("FOUND", t, w.rectangle())
        try:
            kids = w.descendants()
            print("descendants", len(kids))
            for c in kids[:60]:
                ct = c.window_text()
                cn = c.friendly_class_name()
                if ct:
                    print(" ", cn, repr(ct)[:100], c.rectangle())
        except Exception as e:
            print("desc err", e)
