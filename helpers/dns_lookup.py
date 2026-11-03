"""Print a website's public DNS records in plain words."""
import sys

try:
    import dns.resolver
except ImportError:
    sys.exit("The 'dnspython' Python package is missing. Run: python -m pip install -r requirements.txt")

KINDS = [("A", "IP address (v4)"), ("AAAA", "IP address (v6)"), ("CNAME", "Is another name for"),
         ("MX", "Email handled by"), ("NS", "Name servers"), ("TXT", "Text records"),
         ("SOA", "Zone owner record")]


def main(q: str) -> int:
    q = q.strip().removeprefix("http://").removeprefix("https://").split("/")[0]
    r = dns.resolver.Resolver()
    r.lifetime = 10
    for rtype, label in KINDS:
        try:
            ans = r.resolve(q, rtype)
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            continue
        except dns.resolver.NXDOMAIN:
            print(f"{q} does not exist.")
            return 1
        except Exception as e:  # timeouts etc.
            print(f"{label}: could not look up ({e.__class__.__name__})")
            continue
        for rec in ans:
            print(f"{label + ':':<20}{rec.to_text()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
