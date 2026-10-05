import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";

import { API_URL } from "@/config/api";

export const api = axios.create({
	baseURL: API_URL,
	timeout: 20000,
});

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
