/**
 * Classifies a failed request so a screen can tell the three cases apart.
 *
 * Every detail screen previously collapsed these into one outcome and then
 * rendered the "not found" copy anyway:
 *
 * - `reading-detail.tsx` raised an alert reading "Reading not found." while the
 *   body underneath said "No reading selected." -- two contradictions, neither
 *   true, whenever the network was down.
 * - `saint-detail.tsx` discarded the error to the console and rendered
 *   "Saint not found." silently, for a server that had never been reached.
 * - `choir-detail.tsx` discarded the backend's own `detail` string, so the
 *   deliberate `404` that `choir.py` returns for a permission failure
 *   (`can_view_choir_resource`) was indistinguishable from a mistyped id.
 *
 * Distinguishing them is what lets each screen offer the right next action:
 * back-navigation for a genuine 404, a retry button for anything transient.
 */

export type RequestFailureKind = "unauthorized" | "forbidden" | "not-found" | "network" | "server";

export interface RequestFailure {
  kind: RequestFailureKind;
  /** Message safe to show a member: the backend's `detail` when it sent one. */
  message: string;
  /** True when retrying could plausibly succeed without the user changing anything. */
  retryable: boolean;
}

interface AxiosLikeError {
  response?: {
    status?: number;
    data?: { detail?: unknown };
  };
  code?: string;
  message?: string;
  request?: unknown;
}

/**
 * Read `detail` off a failed request and always come back with a string.
 *
 * FastAPI sends `detail` in three shapes:
 *
 * - a string, for failures the endpoint raised itself;
 * - an **array of field errors** for any 422, e.g.
 *   `[{ loc: ["body","password"], msg: "String should have at least 6 characters" }]`;
 * - absent entirely, for a 500 that blew up before it could build a response.
 *
 * The array case is the one that mattered: screens rendered `detail` straight
 * into `<Text>` or `Alert.alert`, so any validation failure handed React an
 * array of objects and the screen died with "Objects are not valid as a React
 * child". Rendering that message was the whole point of the field.
 */
export function detailMessage(error: unknown): string | null {
  const candidate = (error as AxiosLikeError | null)?.response?.data?.detail;

  if (typeof candidate === "string" && candidate.trim()) {
    return candidate.trim();
  }

  if (Array.isArray(candidate)) {
    for (const item of candidate) {
      const message = (item as { msg?: unknown } | null)?.msg;
      if (typeof message === "string" && message.trim()) {
        return message.trim().replace(/^Value error, /i, "");
      }
    }
  }

  return null;
}

/**
 * Turn any thrown request error into a decision the UI can render.
 *
 * `fallbackNotFound` is the copy for a genuine "this does not exist"; it is only
 * ever used for a real 404 so that a transport failure can no longer be reported
 * as missing content.
 */
export function classifyRequestFailure(
  error: unknown,
  options: { fallbackNotFound: string; fallbackMessage?: string },
): RequestFailure {
  const status = (error as AxiosLikeError | null)?.response?.status;
  const detail = detailMessage(error);
  const generic = options.fallbackMessage ?? "Could not reach the server. Check your connection and try again.";

  if (status === 404) {
    return { kind: "not-found", message: detail ?? options.fallbackNotFound, retryable: false };
  }
  if (status === 401) {
    return {
      kind: "unauthorized",
      message: detail ?? "Please sign in to view this.",
      retryable: true,
    };
  }
  if (status === 403) {
    return {
      kind: "forbidden",
      message: detail ?? "You do not have permission to view this.",
      retryable: false,
    };
  }
  if (typeof status === "number") {
    return {
      kind: "server",
      message: detail ?? options.fallbackMessage ?? `The server could not complete that request (${status}).`,
      retryable: true,
    };
  }

  // No response at all: the request never reached the server, or the server's
  // reply was lost. Retrying is the only sensible action.
  return {
    kind: "network",
    message: detail ?? generic,
    retryable: true,
  };
}

/** Build a readable message from an unknown throw for list-screen error banners. */
export function requestErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  const detail = detailMessage(error);
  if (detail) {
    return detail;
  }
  const status = (error as AxiosLikeError | null)?.response?.status;
  if (typeof status === "number") {
    return `The server could not complete that request (${status}).`;
  }
  return fallback;
}