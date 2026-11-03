// Guess what kind of thing was typed, so only the tools that fit are shown.
// The user can always click a different chip; this is only the starting guess.

const COMPANY = /\b(llc|l\.l\.c|inc|corp|corporation|co|company|ltd|limited|lp|llp|plc|group|holdings|partners|gmbh|s\.?a\.?|s\.?a\.? de c\.?v\.?|s\.?r\.?l|ltda|s\.?a\.?s|foundation|bank|trust)\.?$/i;
const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;
const IPV6 = /^[0-9a-f]{0,4}(:[0-9a-f]{0,4}){2,7}$/i;
const VIN = /^[A-HJ-NPR-Z0-9]{17}$/i;
const CRYPTO = /^(0x[a-f0-9]{40}|bc1[a-z0-9]{20,60}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|T[1-9A-HJ-NP-Za-km-z]{33})$/i;
const STREET = /\d+\s+\w+.*\b(st|street|ave|avenue|rd|road|dr|drive|blvd|ln|lane|way|ct|court|hwy|highway|pl|place|calle|avenida|carrera)\b/i;

export function detect(raw) {
  const q = (raw || "").trim();
  if (!q) return null;
  if (/^https?:\/\//i.test(q) || /^www\./i.test(q)) return "link";
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(q)) return "email";
  if (IPV4.test(q) || (q.includes(":") && IPV6.test(q))) return "ip";
  if (CRYPTO.test(q)) return "crypto";
  if (VIN.test(q) && /\d/.test(q) && /[a-z]/i.test(q)) return "vin";
  const digits = q.replace(/\D/g, "");
  if (/^\+?[\d\s().-]+$/.test(q) && digits.length >= 7 && digits.length <= 15) return "phone";
  if (STREET.test(q) || /,\s*[A-Z]{2}\s*\d{5}/.test(q)) return "place";
  if (!/\s/.test(q) && /^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,24}(\/.*)?$/i.test(q)) {
    return q.includes("/") ? "link" : "domain";
  }
  if (/\s/.test(q)) return COMPANY.test(q) ? "company" : "name";
  return "username";
}
