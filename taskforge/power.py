"""Windows power-plan and processor-power-management control via documented powercfg settings.

Every change is preceded by a JSON backup of the values it overwrites so it can be restored.
"""
import glob
import json
import os
import re

from .util import backup_dir, run, timestamp

SUB_PROCESSOR = "54533251-82be-4824-96c1-47b60b740d00"
ULTIMATE_TEMPLATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
KNOWN_SCHEMES = {
    "381b4222-f694-41f0-9685-ff5bb260df2e": "Balanced",
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c": "High performance",
    "a1841308-3541-4fab-bc81-f71556f20b4a": "Power saver",
    ULTIMATE_TEMPLATE: "Ultimate Performance",
}

BOOST_MODES = [
    (0, "Disabled", "Never boosts above base clock. Coolest and quietest, lowest burst performance."),
    (1, "Enabled", "Standard boost when the OS requests more performance."),
    (2, "Aggressive", "Boosts whenever possible. Best responsiveness, most heat/battery drain."),
    (3, "Efficient Enabled", "Boosts only when it is energy-efficient to do so."),
    (4, "Efficient Aggressive", "Aggressive, but prefers efficiency when the gain is small."),
    (5, "Aggressive at Guaranteed", "Aggressive boost, floor at guaranteed (base) clock."),
    (6, "Efficient Aggressive at Guaranteed", "Efficient aggressive boost, floor at guaranteed clock."),
]

# key, GUID, label, kind ('percent' | 'enum'), options, explanation
PROCESSOR_SETTINGS = [
    ("PERFBOOSTMODE", "be337238-0d82-4146-a960-4f3749d470c7", "Processor boost mode (Turbo)", "enum",
     [(v, n) for v, n, _ in BOOST_MODES],
     "Controls how eagerly Windows asks the CPU to enter Intel Turbo Boost / AMD Precision Boost. "
     "'Aggressive' gives the fastest bursts; 'Disabled' caps the CPU at its base clock (great for "
     "quiet/cool laptops). This does NOT raise the CPU's maximum turbo ratio - that is fused or set in BIOS."),
    ("PROCTHROTTLEMAX", "bc5038f7-23e0-4960-96da-33abaf5935ec", "Maximum processor state", "percent", None,
     "Upper limit of CPU performance. 100% allows full turbo. On many systems 99% disables turbo entirely, "
     "a popular trick to cut heat and fan noise on laptops."),
    ("PROCTHROTTLEMIN", "893dee8e-2bef-41e0-89c6-b55d0929964c", "Minimum processor state", "percent", None,
     "Lowest performance the CPU may drop to when idle. Raising it (e.g. 100%) reduces ramp-up latency "
     "slightly but wastes power and heat at idle. Modern CPUs with HWP mostly ignore values above ~5%."),
    ("PERFEPP", "36687f9e-e3a5-4dbf-b1dc-15eb381c6863", "Energy performance preference (EPP)", "percent", None,
     "Hint to the CPU's own frequency controller (Intel Speed Shift / AMD CPPC). 0 = favour performance, "
     "100 = favour energy saving. Lower values ramp clocks faster and hold them higher."),
    ("PERFBOOSTPOL", "45bcc044-d885-43e2-8605-ee0ec6e96b59", "Processor boost policy", "percent", None,
     "How much of the available boost headroom Windows uses (legacy, non-HWP CPUs mostly). 100 = all of it."),
    ("CPMINCORES", "0cc5b647-c1df-4637-891a-dec35c318583", "Core parking - minimum unparked cores", "percent", None,
     "Percentage of cores kept awake. 100% disables core parking so threads never wait for a core to wake. "
     "Helps latency-sensitive games/audio slightly; increases idle power."),
    ("SYSCOOLPOL", "94d3a615-a899-4ac5-ae2b-e4d8f634367f", "System cooling policy", "enum",
     [(0, "Passive (slow CPU before fans)"), (1, "Active (spin fans before slowing CPU)")],
     "Active keeps clocks higher and lets fans do the work; Passive throttles first for silence."),
    ("IDLEDISABLE", "5d76a2ca-e8c0-402f-a133-2158492d58ad", "Processor idle states (C-states)", "enum",
     [(0, "Enabled (normal)"), (1, "Disabled (cores never sleep)")],
     "EXPERT: disabling idle keeps every core at C0. Can shave microseconds of wake-up latency but "
     "sharply increases idle power, heat and may REDUCE turbo headroom. Leave Enabled unless testing."),
]

PRESETS = {
    "Max Turbo": {
        "desc": "Fastest bursts: aggressive boost, EPP 0, no core parking, 100% max state, active cooling. "
                "Expect more heat, fan noise and battery drain.",
        "values": {"PERFBOOSTMODE": 2, "PROCTHROTTLEMAX": 100, "PROCTHROTTLEMIN": 5, "PERFEPP": 0,
                   "PERFBOOSTPOL": 100, "CPMINCORES": 100, "SYSCOOLPOL": 1, "IDLEDISABLE": 0},
    },
    "Responsive Balanced": {
        "desc": "Snappy desktop with sane power: efficient-aggressive boost, EPP 25, light parking.",
        "values": {"PERFBOOSTMODE": 4, "PROCTHROTTLEMAX": 100, "PROCTHROTTLEMIN": 5, "PERFEPP": 25,
                   "PERFBOOSTPOL": 100, "CPMINCORES": 50, "SYSCOOLPOL": 1, "IDLEDISABLE": 0},
    },
    "Cool & Quiet": {
        "desc": "Turbo off (boost disabled, 99% max), EPP 70, passive cooling. Much cooler/quieter, slower bursts.",
        "values": {"PERFBOOSTMODE": 0, "PROCTHROTTLEMAX": 99, "PROCTHROTTLEMIN": 5, "PERFEPP": 70,
                   "PERFBOOSTPOL": 60, "CPMINCORES": 10, "SYSCOOLPOL": 0, "IDLEDISABLE": 0},
    },
    "Battery Saver": {
        "desc": "Maximum battery life: no boost, 80% max state, EPP 90, aggressive parking.",
        "values": {"PERFBOOSTMODE": 0, "PROCTHROTTLEMAX": 80, "PROCTHROTTLEMIN": 0, "PERFEPP": 90,
                   "PERFBOOSTPOL": 0, "CPMINCORES": 5, "SYSCOOLPOL": 0, "IDLEDISABLE": 0},
    },
}

SETTING_BY_KEY = {s[0]: s for s in PROCESSOR_SETTINGS}


class PowerError(Exception):
    pass


def _pc(*args, timeout=30):
    rc, out, err = run(["powercfg", *args], timeout=timeout)
    if rc != 0:
        raise PowerError((err or out).strip() or f"powercfg {' '.join(args)} failed ({rc})")
    return out


def list_schemes():
    """Return [(guid, name, is_active)]."""
    out = _pc("/list")
    res = []
    for line in out.splitlines():
        m = re.search(r"([0-9a-fA-F-]{36})\s+\((.*?)\)\s*(\*)?", line)
        if m:
            res.append((m.group(1).lower(), m.group(2), bool(m.group(3))))
    return res


def active_scheme():
    out = _pc("/getactivescheme")
    m = re.search(r"([0-9a-fA-F-]{36})\s+\((.*?)\)", out)
    return (m.group(1).lower(), m.group(2)) if m else ("", "")


def set_active(guid: str):
    _pc("/setactive", guid)


def create_ultimate():
    """Duplicate the hidden Ultimate Performance template (documented by Microsoft)."""
    out = _pc("-duplicatescheme", ULTIMATE_TEMPLATE)
    m = re.search(r"([0-9a-fA-F-]{36})", out)
    return m.group(1).lower() if m else ""


def read_setting(guid: str, scheme="SCHEME_CURRENT"):
    """Return (ac, dc) current indices, or None if the setting is not exposed on this machine."""
    vals = []
    for q in ("/qh", "/query"):
        try:
            out = _pc(q, scheme, SUB_PROCESSOR, guid)
        except PowerError:
            continue
        vals = re.findall(r"0x([0-9a-fA-F]{8})", out)
        if len(vals) >= 2:
            break
    if len(vals) < 2:
        return None
    return int(vals[-2], 16), int(vals[-1], 16)


def read_all():
    return {key: read_setting(guid) for key, guid, *_ in PROCESSOR_SETTINGS}


def backup(note: str, keys=None) -> str:
    guid, name = active_scheme()
    values = {}
    for key, sguid, *_ in PROCESSOR_SETTINGS:
        if keys and key not in keys:
            continue
        v = read_setting(sguid)
        if v is not None:
            values[key] = v
    data = {"created": timestamp(), "note": note, "scheme_guid": guid, "scheme_name": name, "values": values}
    path = os.path.join(backup_dir(), f"power-{data['created']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def list_backups():
    return sorted(glob.glob(os.path.join(backup_dir(), "power-*.json")), reverse=True)


def apply_values(values: dict, ac=True, dc=True):
    """values: {KEY: int}. Applies to the active scheme and re-activates it."""
    errors = []
    for key, val in values.items():
        sguid = SETTING_BY_KEY[key][1]
        for flag, enabled in (("/setacvalueindex", ac), ("/setdcvalueindex", dc)):
            if not enabled:
                continue
            try:
                _pc(flag, "SCHEME_CURRENT", SUB_PROCESSOR, sguid, str(int(val)))
            except PowerError as e:
                errors.append(f"{key}: {e}")
    _pc("/setactive", "SCHEME_CURRENT")
    return errors


def restore_backup(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    errors = []
    try:
        if data.get("scheme_guid"):
            set_active(data["scheme_guid"])
    except PowerError as e:
        errors.append(f"scheme: {e}")
    for key, (ac, dc) in data.get("values", {}).items():
        if key not in SETTING_BY_KEY:
            continue
        sguid = SETTING_BY_KEY[key][1]
        for flag, val in (("/setacvalueindex", ac), ("/setdcvalueindex", dc)):
            try:
                _pc(flag, "SCHEME_CURRENT", SUB_PROCESSOR, sguid, str(int(val)))
            except PowerError as e:
                errors.append(f"{key}: {e}")
    _pc("/setactive", "SCHEME_CURRENT")
    return data, errors
