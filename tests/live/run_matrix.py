"""Version compatibility matrix: launch every installed ETABS / SAP2000 / SAFE version, run the live suite, record results.

    py run_matrix.py [etabs:22 sap2000:20 ...]      (no args = every installed version)

Safety: a version is skipped if ANY instance of that program is already running (it could be your work).
Only processes started by this script (after launch time) are closed afterwards.
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time

import comtypes.client

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
ROOTS = (r"C:\Program Files\Computers and Structures", r"C:\Program Files (x86)\Computers and Structures")
PROGS = {"etabs": ("ETABS", "ETABS.exe", ["CSI.ETABS.API.ETABSObject"], "t_etabs_live.py"),
         "sap2000": ("SAP2000", "SAP2000.exe", ["CSI.SAP2000.API.SapObject"], "t_csi_live.py"),
         "safe": ("SAFE", "SAFE.exe", ["CSI.SAFE.API.ETABSObject", "CSI.SAFE.API.SAFEObject"], "t_csi_live.py")}


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.strip()


def running(image):
    return [int(x) for x in ps(f"(Get-Process -Name {image[:-4]} -ErrorAction SilentlyContinue).Id").split()]


def kill_new(image, t0, before=()):
    """Close only processes that did not exist before we launched (we verified none were running)."""
    for pid in running(image):
        if pid not in before:
            ps(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue")


def attach(progids):
    for pid in progids:
        try:
            return comtypes.client.GetActiveObject(pid).SapModel
        except Exception:
            pass
    return None


def installs():
    out = []
    for prog, (title, exe, _, test) in PROGS.items():
        for root in ROOTS:
            for d in glob.glob(os.path.join(root, title + "*")):
                p = os.path.join(d, exe)
                if os.path.isfile(p):
                    out.append((prog, os.path.basename(d)[len(title):].strip(), p))
    return sorted(out, key=lambda x: (x[0], x[1]))


def main():
    want = set(a.lower() for a in sys.argv[1:])
    results = []
    for prog, label, exe in installs():
        key = f"{prog}:{label}"
        short = f"{prog}:{label[-2:] if len(label) == 4 else label}"
        if want and key not in want and short not in want:
            continue
        title, image, progids, test = PROGS[prog]
        rec = {"program": title, "install": label, "exe": exe, "started": datetime.datetime.now().isoformat(timespec="seconds")}
        print(f"\n===== {title} {label} =====", flush=True)
        if running(image):
            rec["status"] = "SKIPPED: an instance is already running (not touching it)"
            print(rec["status"], flush=True)
            results.append(rec)
            continue
        t0 = datetime.datetime.now()
        subprocess.Popen([exe], cwd=os.path.dirname(exe), creationflags=0x00000008 | 0x00000200)
        m, ver, lic = None, None, ""
        sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
        from mcpkit import winutil
        for _ in range(60):
            time.sleep(3)
            lic = winutil.license_problem(image)
            if lic:
                break
            m = attach(progids)
            if m:
                try:
                    ver = m.GetVersion()[0]
                    break
                except Exception:
                    m = None
        if lic:
            rec["status"] = "NO LICENSE: " + lic[:160]
            print(rec["status"], flush=True)
            kill_new(image, t0)
            results.append(rec)
            continue
        if not m:
            rec["status"] = "LAUNCH/ATTACH FAILED (API did not answer in 180s)"
            print(rec["status"], flush=True)
            kill_new(image, t0)
            results.append(rec)
            continue
        rec["api_version"] = ver
        print("attached, version", ver, flush=True)
        time.sleep(5)
        args = [sys.executable, os.path.join(HERE, test)] + ([] if prog == "etabs" else [prog])
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=1500, cwd=HERE, env=env)
            text = (p.stdout or "") + ("\n[stderr]\n" + p.stderr[-1500:] if p.returncode and p.stderr else "")
        except subprocess.TimeoutExpired as e:
            text = (e.stdout or b"").decode("utf8", "ignore") if isinstance(e.stdout, bytes) else (e.stdout or "")
            text += "\n[TIMEOUT after 1500s]"
        with open(os.path.join(OUT, f"{prog}_{label}.log"), "w", encoding="utf-8") as fh:
            fh.write(text)
        m_ = re.search(r"RESULT[^:]*:\s*(\d+) passed,\s*(\d+) failed", text)
        rec["passed"], rec["failed"] = (int(m_.group(1)), int(m_.group(2))) if m_ else (None, None)
        rec["failures"] = [l.strip()[:200] for l in text.splitlines() if l.startswith("FAIL")]
        rec["status"] = "OK" if m_ and rec["failed"] == 0 else ("PARTIAL" if m_ else "SUITE DID NOT FINISH")
        print(rec["status"], rec["passed"], rec["failed"], flush=True)
        kill_new(image, t0)
        time.sleep(5)
        results.append(rec)
        with open(os.path.join(OUT, "matrix.json"), "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
    with open(os.path.join(OUT, "matrix.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
