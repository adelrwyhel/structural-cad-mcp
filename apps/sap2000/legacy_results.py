"""Legacy result readers for SAP2000 versions WITHOUT the DatabaseTables API (e.g. v20).  *** UNVERIFIED ***

Written from the CSI Results.* API reference; never run against a real old installation (the only v20 install used
for development had no license). Signatures follow the documented order: outputs are returned as a tuple that ends
with the return code. Each reader returns (columns, rows) shaped like the table readers.
"""

KEYS = ("Joint Reactions", "Joint Displacements", "Base Reactions", "Modal Periods And Frequencies",
        "Element Forces - Frames")


def _ok(r, what):
    if r[-1] != 0:
        raise RuntimeError(f"legacy Results call '{what}' failed (code {r[-1]}); the model must be analyzed")
    return r[:-1]


def _rows(*cols):
    return [list(map(lambda x: "" if x is None else str(x), row)) for row in zip(*cols)]


def fetch(m, key):
    res = m.Results
    try:
        if key == "Joint Reactions":
            o = _ok(res.JointReact("ALL", 2, 0, [], [], [], [], [], [], [], [], [], [], []), "JointReact")
            return (["Joint", "OutputCase", "StepType", "StepNum", "F1", "F2", "F3", "M1", "M2", "M3"],
                    _rows(o[1], o[3], o[4], o[5], o[6], o[7], o[8], o[9], o[10], o[11]))
        if key == "Joint Displacements":
            o = _ok(res.JointDispl("ALL", 2, 0, [], [], [], [], [], [], [], [], [], [], []), "JointDispl")
            return (["Joint", "OutputCase", "StepType", "StepNum", "U1", "U2", "U3", "R1", "R2", "R3"],
                    _rows(o[1], o[3], o[4], o[5], o[6], o[7], o[8], o[9], o[10], o[11]))
        if key == "Base Reactions":
            o = _ok(res.BaseReact(0, [], [], [], [], [], [], [], [], [], 0, 0, 0), "BaseReact")
            return (["OutputCase", "StepType", "StepNum", "GlobalFX", "GlobalFY", "GlobalFZ", "GlobalMX", "GlobalMY", "GlobalMZ"],
                    _rows(o[1], o[2], o[3], o[4], o[5], o[6], o[7], o[8], o[9]))
        if key == "Modal Periods And Frequencies":
            o = _ok(res.ModalPeriod(0, [], [], [], [], [], [], []), "ModalPeriod")
            return (["OutputCase", "StepType", "StepNum", "Period", "Frequency", "CircFreq", "Eigenvalue"],
                    _rows(o[1], o[2], o[3], o[4], o[5], o[6], o[7]))
        if key == "Element Forces - Frames":
            o = _ok(res.FrameForce("ALL", 2, 0, [], [], [], [], [], [], [], [], [], [], [], [], []), "FrameForce")
            return (["Frame", "Station", "OutputCase", "StepType", "StepNum", "P", "V2", "V3", "T", "M2", "M3"],
                    _rows(o[1], o[2], o[5], o[6], o[7], o[8], o[9], o[10], o[11], o[12], o[13]))
    except RuntimeError:
        raise
    except Exception as e:  # noqa
        raise RuntimeError(f"legacy reader for '{key}' failed ({type(e).__name__}: {e}). These readers are UNVERIFIED "
                           f"on old versions; the call signature may differ.")
    raise RuntimeError(f"no legacy reader for table '{key}'. Available: {', '.join(KEYS)}")
