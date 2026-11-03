"""Print what can be read from a phone number itself (no internet needed)."""
import sys

try:
    import phonenumbers
    from phonenumbers import carrier, geocoder, timezone
except ImportError:
    sys.exit("The 'phonenumbers' Python package is missing. Run: python -m pip install -r requirements.txt")

KINDS = {0: "Landline", 1: "Mobile", 2: "Landline or mobile", 3: "Toll-free", 4: "Premium rate",
         5: "Shared cost", 6: "Internet phone (VoIP)", 7: "Personal number", 8: "Pager",
         9: "Company number", 10: "Voicemail", 99: "Unknown"}


def main(raw: str) -> int:
    try:
        n = phonenumbers.parse(raw, "US")
    except phonenumbers.NumberParseException as e:
        print(f"Could not read that as a phone number: {e}")
        return 1
    print(f"Number:        {phonenumbers.format_number(n, phonenumbers.PhoneNumberFormat.INTERNATIONAL)}")
    print(f"Real number:   {'yes' if phonenumbers.is_valid_number(n) else 'no (not a number that can be assigned)'}")
    print(f"Country:       {geocoder.country_name_for_number(n, 'en') or 'unknown'} (+{n.country_code})")
    print(f"Area:          {geocoder.description_for_number(n, 'en') or 'unknown'}")
    print(f"Type:          {KINDS.get(phonenumbers.number_type(n), 'Unknown')}")
    print(f"First carrier: {carrier.name_for_number(n, 'en') or 'unknown'}"
          "  (the company it was first given out by; it may have been moved since)")
    print(f"Time zone:     {', '.join(timezone.time_zones_for_number(n)) or 'unknown'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
