"""Small Windows helpers (pywin32): detect dialogs shown by a program, e.g. a missing-license message."""
import subprocess


def pids_of(image: str) -> set:
    """PIDs of running processes with this image name (e.g. 'SAP2000.exe')."""
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == image.lower():
            try:
                pids.add(int(parts[1].strip('"')))
            except ValueError:
                pass
    return pids


def program_dialogs(image: str) -> list:
    """Visible standard dialogs (class #32770) owned by the program: [(title, text), ...]."""
    import win32gui
    import win32process
    pids = pids_of(image)
    found = []

    def on_window(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == "#32770":
                if win32process.GetWindowThreadProcessId(hwnd)[1] in pids:
                    texts = []
                    win32gui.EnumChildWindows(hwnd, lambda h, _: texts.append(win32gui.GetWindowText(h)) or True, None)
                    found.append((win32gui.GetWindowText(hwnd), " ".join(t for t in texts if t).strip()))
        except Exception:
            pass
        return True

    win32gui.EnumWindows(on_window, None)
    return found


def license_problem(image: str) -> str:
    """Text of a license-related dialog shown by the program, or ''."""
    for title, text in program_dialogs(image):
        blob = f"{title} {text}".lower()
        if "licens" in blob:
            return text or title
    return ""
