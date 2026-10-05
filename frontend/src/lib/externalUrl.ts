/**
 * Validation for a URL before it is handed to the operating system.
 *
 * `file_url` on a choir resource is a value this client does not control: it
 * comes from the API, and in a database with any third-party or manually entered
 * row it can be anything. Passing such a value straight to `Linking.openURL`
 * asks the OS to handle an arbitrary scheme -- `tel:`, `sms:`, `file:`,
 * `data:`, or an app deep link -- from a tap the member believed was opening a
 * PDF or an MP3.
 *
 * Only web URLs are accepted. Anything else, and anything unparseable, returns
 * `null` so the caller can explain itself rather than launching whatever the
 * string said.
 */

const WEB_SCHEMES = new Set(["http:", "https:"]);

/**
 * Resolve `value` against `base` and return it only if it is an http(s) URL.
 *
 * `base` lets a relative path such as `/api/choir/12/file` resolve against the
 * configured API origin. Returns `null` for an empty value, a non-string, an
 * unparseable URL, or a scheme outside the allowlist.
 */
export function safeExternalUrl(value: unknown, base?: string): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  let parsed: URL;
  try {
    // `base` is required to parse a relative reference; without one, a relative
    // URL simply has nothing to resolve against and is rejected.
    parsed = new URL(trimmed, base);
  } catch {
    return null;
  }

  if (!WEB_SCHEMES.has(parsed.protocol)) {
    return null;
  }
  return parsed.toString();
}

/** Whether `value` is an http(s) URL, without resolving it against a base. */
export function isWebUrl(value: unknown): boolean {
  return safeExternalUrl(value, "https://invalid.local") !== null;
}