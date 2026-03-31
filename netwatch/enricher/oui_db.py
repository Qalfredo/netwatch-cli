"""IEEE OUI vendor lookup.

The lookup table below is a curated subset of the IEEE MA-L (OUI) registry
covering the most common residential gateway / modem / router vendors.

For a full database (~30 000 entries) run:
    python scripts/download_oui.py
which writes netwatch/enricher/oui_full.json.gz; this module loads it
automatically when present.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Bundled minimal OUI table (6-hex-char key, upper-case, no separators)
# ---------------------------------------------------------------------------
_BUILTIN: dict[str, str] = {
    # Apple
    "000393": "Apple",
    "000502": "Apple",
    "000A27": "Apple",
    "000A95": "Apple",
    "001124": "Apple",
    "001451": "Apple",
    "0016CB": "Apple",
    "001731": "Apple",
    "001B63": "Apple",
    "001CF0": "Apple",
    "001E52": "Apple",
    "001FF3": "Apple",
    "002312": "Apple",
    "002608": "Apple",
    "3C0754": "Apple",
    "70CD60": "Apple",
    "A45E60": "Apple",
    # Cisco Systems
    "00000C": "Cisco Systems",
    "000010": "Cisco Systems",
    "00001B": "Cisco Systems",
    "00002A": "Cisco Systems",
    "000142": "Cisco Systems",
    "000BFC": "Cisco Systems",
    "0013C4": "Cisco Systems",
    "001A2F": "Cisco Systems",
    "687F74": "Cisco Systems",
    "84D47E": "Cisco Systems",
    "000641": "Cisco-Linksys",
    "000C41": "Cisco-Linksys",
    "00216A": "Cisco-Linksys",
    "002369": "Cisco-Linksys",
    # D-Link
    "00055D": "D-Link",
    "000D88": "D-Link",
    "001195": "D-Link",
    "1C5F2B": "D-Link",
    "34EA34": "D-Link",
    "84C9B2": "D-Link",
    "B09CE4": "D-Link",
    "C8BE19": "D-Link",
    # Huawei Technologies
    "001882": "Huawei Technologies",
    "00E0FC": "Huawei Technologies",
    "04C06F": "Huawei Technologies",
    "0C37DC": "Huawei Technologies",
    "1090FA": "Huawei Technologies",
    "1C1D67": "Huawei Technologies",
    "2C55D3": "Huawei Technologies",
    "400101": "Huawei Technologies",
    "5C4CA9": "Huawei Technologies",
    "5CEA1D": "Huawei Technologies",
    "6416F0": "Huawei Technologies",
    "708A09": "Huawei Technologies",
    "8C34FD": "Huawei Technologies",
    "9C742A": "Huawei Technologies",
    "AC853D": "Huawei Technologies",
    "B8BC1B": "Huawei Technologies",
    "C8D15E": "Huawei Technologies",
    "F46920": "Huawei Technologies",
    # TP-Link Technologies
    "50C7BF": "TP-Link Technologies",
    "54A703": "TP-Link Technologies",
    "6032B1": "TP-Link Technologies",
    "A42BB0": "TP-Link Technologies",
    "B0A7B9": "TP-Link Technologies",
    "C025E9": "TP-Link Technologies",
    "D46E5C": "TP-Link Technologies",
    "E848B8": "TP-Link Technologies",
    "F8D111": "TP-Link Technologies",
    # Netgear
    "00095B": "NETGEAR",
    "00146C": "NETGEAR",
    "00184D": "NETGEAR",
    "20E52A": "NETGEAR",
    "3491BF": "NETGEAR",
    "6CB0CE": "NETGEAR",
    "A040A0": "NETGEAR",
    "C03F0E": "NETGEAR",
    "E04136": "NETGEAR",
    # ASUS
    "000C6E": "ASUSTek Computer",
    "049226": "ASUSTek Computer",
    "08606E": "ASUSTek Computer",
    "10BF48": "ASUSTek Computer",
    "2C4D54": "ASUSTek Computer",
    "50465D": "ASUSTek Computer",
    "74D02B": "ASUSTek Computer",
    "AC220B": "ASUSTek Computer",
    "F8328C": "ASUSTek Computer",
    # MikroTik
    "000C42": "MikroTik",
    "2CC81B": "MikroTik",
    "64D154": "MikroTik",
    "6C3B6B": "MikroTik",
    "B8693F": "MikroTik",
    "DC2C6E": "MikroTik",
    "E48D8C": "MikroTik",
    # ZyXEL Communications
    "001349": "ZyXEL Communications",
    "0019CB": "ZyXEL Communications",
    "00A0C5": "ZyXEL Communications",
    "001E5B": "ZyXEL Communications",
    "602AD0": "ZyXEL Communications",
    "9CB2B2": "ZyXEL Communications",
    "BCC43B": "ZyXEL Communications",
    # ARRIS Group
    "0019A6": "ARRIS Group",
    "001AC2": "ARRIS Group",
    "002590": "ARRIS Group",
    "7CF14B": "ARRIS Group",
    "BC1401": "ARRIS Group",
    # Technicolor / Thomson
    "0014BF": "Technicolor",
    "001CA2": "Technicolor",
    "00247B": "Technicolor",
    "004889": "Technicolor",
    "74B57E": "Technicolor",
    # Belkin International
    "001E58": "Belkin International",
    "08863B": "Belkin International",
    "944452": "Belkin International",
    "E83E08": "Belkin International",
    # Ubiquiti Networks
    "001FE2": "Ubiquiti Networks",
    "006867": "Ubiquiti Networks",
    "0418D6": "Ubiquiti Networks",
    "24A43C": "Ubiquiti Networks",
    "44D9E7": "Ubiquiti Networks",
    "78D280": "Ubiquiti Networks",
    "80240B": "Ubiquiti Networks",
    "DC9FDB": "Ubiquiti Networks",
    "F09FC2": "Ubiquiti Networks",
    # Raspberry Pi
    "B827EB": "Raspberry Pi Foundation",
    "DCA632": "Raspberry Pi Trading",
    "E45F01": "Raspberry Pi Trading",
    # VMware / VirtualBox (common in test environments)
    "005056": "VMware",
    "000C29": "VMware",
    "000569": "VMware",
    "080027": "Oracle VirtualBox",
    # Motorola / ARRIS
    "001CD8": "Motorola Mobility",
    "B4CE36": "Motorola",
    # Sagemcom
    "002269": "Sagemcom",
    "5CA4B4": "Sagemcom",
    "C83A35": "Sagemcom",
    # Ericsson
    "001CE8": "Ericsson",
    "0024BF": "Ericsson",
    "3CAAB9": "Ericsson",
    # Nokia
    "001ED9": "Nokia",
    "002454": "Nokia",
    "F01FAF": "Nokia",
    # Movistar / Telefónica
    "00236C": "Askey Computer",
    "0050FC": "Askey Computer",
}

_FULL_DB_PATH = Path(__file__).parent / "oui_full.json.gz"
_db: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _db
    if _db is not None:
        return _db
    if _FULL_DB_PATH.exists():
        try:
            with gzip.open(_FULL_DB_PATH, "rt", encoding="utf-8") as fh:
                _db = json.load(fh)
                return _db
        except Exception:  # noqa: BLE001
            pass
    _db = _BUILTIN
    return _db


def lookup(mac_address: str) -> str | None:
    """Return the vendor name for *mac_address*, or ``None`` if unknown.

    *mac_address* may use any separator (``:``, ``-``, ``·``) or none.
    Only the first three octets (OUI prefix) are used.
    """
    clean = mac_address.upper().replace(":", "").replace("-", "").replace(".", "")
    if len(clean) < 6:
        return None
    oui = clean[:6]
    return _load().get(oui)
