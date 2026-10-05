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

function detailOf(error: unknown): string | null {
  const candidate = (error as AxiosLikeError | null)?.response?.data?.detail;
  if (typeof candidate === "string" && candidate.trim()) {
    return candidate.trim();
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
  const detail = detailOf(error);
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
  const detail = detailOf(error);
  if (detail) {
    return detail;
  }
  const status = (error as AxiosLikeError | null)?.response?.status;
  if (typeof status === "number") {
    return `The server could not complete that request (${status}).`;
  }
  return fallback;
}