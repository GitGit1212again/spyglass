"""Decode a vehicle VIN with the free US government (NHTSA) database."""
import json
import ssl
import sys
import urllib.request

try:
    import certifi
except ImportError:
    sys.exit("The 'certifi' Python package is missing. Run: python -m pip install -r requirements.txt")

SSL = ssl.create_default_context(cafile=certifi.where())

FIELDS = [("ModelYear", "Year"), ("Make", "Make"), ("Model", "Model"), ("Trim", "Trim"),
          ("BodyClass", "Body"), ("VehicleType", "Type"), ("DisplacementL", "Engine (litres)"),
          ("FuelTypePrimary", "Fuel"), ("Manufacturer", "Built by"), ("PlantCity", "Plant city"),
          ("PlantState", "Plant state"), ("PlantCountry", "Plant country"), ("ErrorText", "Notes")]


def main(vin: str) -> int:
    vin = vin.strip().upper()
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
    with urllib.request.urlopen(url, timeout=30, context=SSL) as r:
        d = json.load(r)["Results"][0]
    print(f"VIN:  {vin}")
    for key, label in FIELDS:
        v = (d.get(key) or "").strip()
        if v and v != "0":
            print(f"{label + ':':<17}{v}")
    print("\nTheft and total-loss check (free): https://www.nicb.org/vincheck")
    print("Open recalls: https://www.nhtsa.gov/recalls?vin=" + vin)
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
