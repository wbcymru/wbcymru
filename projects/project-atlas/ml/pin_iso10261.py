"""ISO 10261 Product Identification Number (PIN) parser/validator.

Earth-moving/construction machinery uses a 17-character PIN (distinct from
the automotive 17-char VIN under ISO 3779) structured as:
  1-3   WMC  World Manufacturer Code   (assigned by AEM)
  4-8   MDS  Machine Descriptor Section (left-padded with zeros if short)
  9     CL   Check Letter               (Modulus-23 check over the other 16 chars)
  10-17 MIS  Machine Indicator Section  (serial/year/plant, OEM-specific)

Character set: digits 0-9 plus uppercase A-Z EXCLUDING I, O, Q (visually
confusable with 1/0), giving 33 valid characters total. Physical nameplates
bound the PIN with protection symbols (e.g. *...* or ><...><) to prevent
leading/trailing character fraud -- that's a physical-marking convention,
not something this module encodes as data.

CAVEAT: no authoritative AEM/ISO 10261 weight table or letter-value mapping
was available while writing this. The Modulus-23 scheme below is a
documented, internally self-consistent implementation (it validates its own
computed check letters) but has NOT been verified against a real OEM
nameplate. Treat compute/validate results as illustrative until checked
against known-good PINs from an authoritative source.
"""

DIGITS = "0123456789"
LETTERS23 = "ABCDEFGHJKLMNPRSTUVWXYZ"  # A-Z minus I, O, Q -- 23 letters
CHARSET = DIGITS + LETTERS23  # 33 valid PIN characters

# 16 weights for the 16 non-check-letter positions (WMC+MDS then MIS), applied
# in PIN left-to-right order skipping position 9. Arbitrary but documented --
# see module caveat above.
WEIGHTS = list(range(16, 0, -1))


class InvalidPIN(ValueError):
    pass


def _char_value(c: str) -> int:
    try:
        return CHARSET.index(c)
    except ValueError:
        raise InvalidPIN(f"character {c!r} not valid in an ISO 10261 PIN (digits or A-Z minus I/O/Q only)")


def parse_pin(pin: str) -> dict:
    """Split a 17-char PIN into its WMC/MDS/check_letter/MIS segments.

    Returns a dict shaped for asset_identity.decode_input.parsed_segments.
    """
    if len(pin) != 17:
        raise InvalidPIN(f"PIN must be exactly 17 characters, got {len(pin)}")
    for c in pin:
        _char_value(c)  # raises on invalid character
    return {
        "wmc": pin[0:3],
        "mds": pin[3:8],
        "check_letter": pin[8],
        "mis": pin[9:17],
    }


def compute_check_letter(pin: str) -> str:
    """Recompute the expected check letter (position 9) from the other 16 chars."""
    if len(pin) != 17:
        raise InvalidPIN(f"PIN must be exactly 17 characters, got {len(pin)}")
    payload = pin[0:8] + pin[9:17]  # 16 chars: WMC+MDS, then MIS
    weighted_sum = sum(_char_value(c) * w for c, w in zip(payload, WEIGHTS))
    return LETTERS23[weighted_sum % 23]


def validate_check_letter(pin: str) -> bool:
    """True if pin[8] matches the Modulus-23 check letter computed from the rest."""
    return compute_check_letter(pin) == pin[8]


if __name__ == "__main__":
    # Self-test: build a PIN with an arbitrary payload, compute its check
    # letter, then confirm validate_check_letter round-trips. This proves
    # internal consistency; it does NOT prove conformance to a real OEM's
    # actual PINs (no authoritative reference was available -- see caveat).
    sample_payload_wmc_mds = "CAT" + "0259D"  # 3 + 5 = 8 chars
    sample_mis = "3G012345"  # 8 chars
    provisional = sample_payload_wmc_mds + "A" + sample_mis  # placeholder check letter
    check = compute_check_letter(provisional)
    full_pin = sample_payload_wmc_mds + check + sample_mis
    print("Constructed PIN:", full_pin)
    print("parse_pin:", parse_pin(full_pin))
    print("validate_check_letter:", validate_check_letter(full_pin))
    assert validate_check_letter(full_pin), "self-test failed: check letter did not round-trip"
    # Tamper with one MIS digit and confirm validation now fails.
    tampered = full_pin[:-1] + ("1" if full_pin[-1] != "1" else "2")
    print("tampered PIN validates:", validate_check_letter(tampered), "(expected False)")
    assert not validate_check_letter(tampered), "self-test failed: tampering was not detected"
    print("All self-tests passed.")
