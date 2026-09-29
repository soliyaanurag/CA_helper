"""States and GSTINs: the GST state list and the checks a GSTIN must pass.

    GST_STATES                      [{"name": "Maharashtra", "code": "27"}, ...]
    state_code("Maharashtra")       "27" (None for a name not in the list)
    gstin_error(gstin, pan, state)  None if the GSTIN is fine, else what is wrong

The state list is reference data in content/reference/gst_states.json (with its
source note: checked against the GST e-invoice portal's state codes). A GSTIN is
<state code 2><PAN 10><entity 1>Z<check character 1>; the check character comes
from the other 14 with the mod-36 algorithm below.
"""

import json

from app.config import REPO_ROOT

_STATES_FILE = REPO_ROOT / "content" / "reference" / "gst_states.json"
GST_STATES = json.loads(_STATES_FILE.read_text())["states"]
_CODE_OF = {state["name"]: state["code"] for state in GST_STATES}

_CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def state_code(name: str) -> str | None:
    """The GST code of a state or union territory, e.g. "27" for Maharashtra."""
    return _CODE_OF.get(name)


def gstin_check_character(first_14: str) -> str:
    """The 15th character of a GSTIN: every character's value (0-9, A-Z = 0-35) is
    multiplied by 1 and 2 in turn; the digits of each product in base 36 are added up;
    the check character makes the total a multiple of 36."""
    total = 0
    for index, character in enumerate(first_14):
        product = _CHARACTERS.index(character) * (1 if index % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _CHARACTERS[(36 - total % 36) % 36]


def gstin_error(gstin: str, pan: str | None, state: str) -> str | None:
    """What is wrong with a (well-formed) GSTIN for this PAN and state, or None."""
    if gstin_check_character(gstin[:14]) != gstin[14]:
        return "This GSTIN is not valid: its last character does not match. Check for a typo."
    code = state_code(state)
    if code is not None and gstin[:2] != code:
        return f"This GSTIN starts with {gstin[:2]}, but the code of {state} is {code}."
    if pan and gstin[2:12] != pan:
        return "The PAN inside this GSTIN (characters 3 to 12) does not match your PAN."
    return None
