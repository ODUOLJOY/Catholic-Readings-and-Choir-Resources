import AsyncStorage from "@react-native-async-storage/async-storage";
import axios, { InternalAxiosRequestConfig } from "axios";

import { API_URL } from "@/config/api";

export const api = axios.create({
	baseURL: API_URL,
	timeout: 20000,
});

/*
 * Transient-failure retry with jittered exponential backoff.
 *
 * When the backend runs on Render it may return 503 (free-tier suspension /
 * resource limits), 502 (cold start), or 429 (rate limiting). All are
 * transient: a retry a few seconds later usually succeeds once the service
 * has finished waking up or the rate limiter has cooled down.
 *
 * The interceptor retries GET/HEAD/OPTIONS requests that failed for network
 * errors (CORS block at the infra level, timeout) or any status in
 * RETRYABLE_STATUS, with jittered backoff so retries are staggered rather than
 * firing in a synchronized burst.
 *
 * IMPORTANT — jitter prevents retry storms: without randomness, when N
 * requests fail simultaneously they all retry at exactly the same moment,
 * creating a thundering herd that trips the 429 rate limiter and triggers
 * more retries in a positive-feedback loop. Full jitter (50–150% of the
 * computed delay) breaks that cycle.
 *
 * 429s get a longer base delay (5 s vs 1 s) and optionally honour the
 * server's Retry-After header. They also retry only once (MAX_RETRIES_429)
 * instead of three times, because a 429 is the backend explicitly telling us
 * to slow down — hammering it harder makes the problem worse.
 */
const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
const MAX_RETRIES = 3;
const RETRY_BASE_DELAY = 1000; // ms — base for 5xx / timeout
const RATE_LIMIT_BASE_DELAY = 5000; // ms — longer base for 429
const MAX_RETRIES_429 = 1; // don't hammer a rate-limited backend

function isRetryable(error: unknown): boolean {
	const axiosErr = error as { response?: { status?: number }; code?: string };
	if (axiosErr.response) {
		return RETRYABLE_STATUS.has(axiosErr.response.status ?? 0);
	}
	// No response means the request never reached the server (network error,
	// CORS block at the infra level, timeout) -- retryable.
	return true;
}

function isRetryableMethod(method: string): boolean {
	return ["get", "head", "options"].includes(method.toLowerCase());
}

/** Random multiplier in [0.5, 1.5] for full jitter. */
function jitter(): number {
	return 0.5 + Math.random();
}

/**
 * Compute the retry delay for a given attempt, with jitter.
 *
 * - 429 responses honour the `Retry-After` header (seconds) when present,
 *   then fall back to a longer 5 s base with jitter.
 * - All other retryable errors use the standard 1 s base with jitter.
 */
function retryDelay(error: unknown, attempt: number): number {
	const axiosErr = error as {
		response?: { status?: number; headers?: Record<string, string> };
	};
	const status = axiosErr.response?.status;

	if (status === 429) {
		const retryAfter =
			axiosErr.response?.headers?.["retry-after"] ??
			axiosErr.response?.headers?.["Retry-After"];
		if (retryAfter) {
			const parsed = parseFloat(retryAfter);
			if (!isNaN(parsed)) return Math.round(parsed * 1000 * jitter());
		}
		return Math.round(RATE_LIMIT_BASE_DELAY * Math.pow(2, attempt) * jitter());
	}

	return Math.round(RETRY_BASE_DELAY * Math.pow(2, attempt) * jitter());
}

/** Retry interceptor: retries GET/HEAD/OPTIONS on transient failures. */
api.interceptors.response.use(undefined, async (error) => {
	const config = error?.config as
		| (InternalAxiosRequestConfig & { _retryCount?: number })
		| undefined;
	const method = (config?.method ?? "get").toLowerCase();

	if (!config || !isRetryableMethod(method) || !isRetryable(error)) {
		return Promise.reject(error);
	}

	const status = (error as { response?: { status?: number } })?.response?.status;
	const maxRetries = status === 429 ? MAX_RETRIES_429 : MAX_RETRIES;
	const attempt = config._retryCount ?? 0;

	if (attempt >= maxRetries) {
		return Promise.reject(error);
	}

	config._retryCount = attempt + 1;
	const delay = retryDelay(error, attempt);

	await new Promise((resolve) => setTimeout(resolve, delay));

	return api(config);
});

/**
 * Run an array of request promises with a concurrency limit.
 *
 * The Choir screen fires 5 shelf requests + categories + favorites + liturgy
 * (8 total) simultaneously on load. When the backend is slow the retry
 * interceptor retries all of them, multiplying the load. Batching with a
 * limit ensures only N requests are in flight at once, so the retry storm
 * never exceeds N × retries concurrent requests.
 *
 * Usage:
 *   const results = await fetchConcurrent(
 *     [fetchCategories(), fetchResources(...), ...],
 *     4,
 *   );
 */
export async function fetchConcurrent<T>(
	requests: Promise<T>[],
	limit = 4,
): Promise<T[]> {
	if (requests.length <= limit) {
		return Promise.all(requests);
	}

	const results: T[] = new Array(requests.length);
	const executing: Promise<void>[] = [];

	for (let i = 0; i < requests.length; i++) {
		const promise = requests[i].then((result) => {
			results[i] = result;
		});
		executing.push(promise);

		if (executing.length >= limit) {
			await Promise.race(executing).then(() => {
				const idx = executing.findIndex((p) => p === promise);
				if (idx !== -1) executing.splice(idx, 1);
			});
		}
	}

	await Promise.all(executing);
	return results;
}

let refreshPromise: Promise<string> | null = null;

type SessionListener = (sessionActive: boolean) => void;
const sessionListeners = new Set<SessionListener>();

/**
 * Observe session validity changes so the UI can show a logged-out state.
 *
 * Previously a session that was cleared by a failed refresh was invisible to the
 * rest of the app: screens kept rendering as if signed in and just displayed
 * whatever error the next request produced.
 */
export function onSessionChange(listener: SessionListener): () => void {
	sessionListeners.add(listener);
	return () => {
		sessionListeners.delete(listener);
	};
}

function emitSessionChange(sessionActive: boolean) {
	for (const listener of sessionListeners) {
		listener(sessionActive);
	}
}

async function clearStoredSession() {
	await AsyncStorage.multiRemove([
		"access_token",
		"refresh_token",
		"user",
		"user_role",
	]);
	emitSessionChange(false);
}

async function refreshAccessToken(): Promise<string> {
	const refreshToken = await AsyncStorage.getItem("refresh_token");
	if (!refreshToken) {
		throw new Error("No refresh token available.");
	}

	const response = await api.post("/api/auth/refresh", {
		refresh_token: refreshToken,
	});
	const accessToken = response.data?.access_token;

	if (!accessToken) {
		throw new Error("Refresh response did not include an access token.");
	}

	await AsyncStorage.setItem("access_token", accessToken);
	if (response.data?.refresh_token) {
		await AsyncStorage.setItem("refresh_token", response.data.refresh_token);
	}

	return accessToken;
}

api.interceptors.request.use(async (config) => {
	const token = await AsyncStorage.getItem("access_token");

	if (token) {
		config.headers.Authorization = `Bearer ${token}`;
	}

	return config;
});

api.interceptors.response.use(
	(response) => response,
	async (error) => {
		const request = error.config as typeof error.config & {
			_retry?: boolean;
		};

		if (
			error.response?.status !== 401 ||
			!request ||
			request._retry ||
			request?.url?.includes("/api/auth/login") ||
			request?.url?.includes("/api/auth/refresh")
		) {
			return Promise.reject(error);
		}

		request._retry = true;

		// A logged-out visitor has nothing to refresh. Without this guard every
		// protected request from a signed-out session produced a pointless
		// refresh attempt that failed with "No refresh token available.", which
		// surfaced as the error the member saw instead of the real 401.
		const hasRefreshToken = await AsyncStorage.getItem("refresh_token");
		if (!hasRefreshToken) {
			return Promise.reject(error);
		}

		try {
			if (!refreshPromise) {
				refreshPromise = refreshAccessToken().finally(() => {
					refreshPromise = null;
				});
			}

			const accessToken = await refreshPromise;
			request.headers = request.headers ?? {};
			request.headers.Authorization = `Bearer ${accessToken}`;
			emitSessionChange(true);
			return api(request);
		} catch (refreshError) {
			if (
				axios.isAxiosError(refreshError) &&
				refreshError.response &&
				[400, 401, 403].includes(refreshError.response.status)
			) {
				// The stored session is genuinely no longer usable.
				await clearStoredSession();
			}
			return Promise.reject(refreshError);
		}
	}
);
