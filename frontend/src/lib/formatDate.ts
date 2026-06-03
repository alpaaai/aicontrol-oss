/**
 * Format an ISO timestamp string in the given IANA timezone.
 * Falls back to UTC if the timezone is invalid.
 */
export function formatTs(
  iso: string,
  timezone: string,
  opts: Intl.DateTimeFormatOptions = {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }
): string {
  try {
    return new Date(iso).toLocaleString("en-US", { ...opts, timeZone: timezone });
  } catch {
    return new Date(iso).toLocaleString("en-US", { ...opts, timeZone: "UTC" });
  }
}
