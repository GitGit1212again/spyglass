"""Print the public registration record for a website or IP address."""
import ipaddress
import json
import ssl
import sys
import urllib.request

try:
    import certifi
    import whois
except ImportError:
    sys.exit("A required Python package (certifi or python-whois) is missing. "
             "Run: python -m pip install -r requirements.txt")

SSL = ssl.create_default_context(cafile=certifi.where())

FIELDS = [("domain_name", "Website"), ("registrar", "Registered through"), ("creation_date", "Created"),
          ("updated_date", "Last changed"), ("expiration_date", "Expires"), ("name", "Owner name"),
          ("org", "Owner organisation"), ("address", "Address"), ("city", "City"), ("state", "State"),
          ("country", "Country"), ("emails", "Contact emails"), ("name_servers", "Name servers"),
          ("status", "Status")]


def show(v):
    if isinstance(v, (list, tuple, set)):
        seen = []
        for x in v:
            s = str(x)
            if s.lower() not in [t.lower() for t in seen]:
                seen.append(s)
        return ", ".join(seen)
    return str(v)


def ip_record(ip: str) -> int:
    # RDAP is the modern whois for IP blocks; ARIN redirects to the right registry.
    with urllib.request.urlopen(f"https://rdap.arin.net/registry/ip/{ip}", timeout=20, context=SSL) as r:
        d = json.load(r)
    print(f"IP block:  {d.get('startAddress')} - {d.get('endAddress')}")
    print(f"Name:      {d.get('name')}")
    print(f"Country:   {d.get('country', 'unknown')}")
    for ent in d.get("entities", []):
        card = ent.get("vcardArray", [None, []])[1]
        fn = next((c[3] for c in card if c[0] == "fn"), None)
        if fn:
            print(f"Held by:   {fn}  ({', '.join(ent.get('roles', []))})")
    return 0


def main(q: str) -> int:
    q = q.strip().removeprefix("http://").removeprefix("https://").split("/")[0]
    try:
        ipaddress.ip_address(q)
        return ip_record(q)
    except ValueError:
        pass
    w = whois.whois(q)
    any_ = False
    for key, label in FIELDS:
        v = w.get(key)
        if v:
            any_ = True
            print(f"{label + ':':<20}{show(v)}")
    if not any_:
        print("No registration record came back. The site may not exist, or its registry hides everything.")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
