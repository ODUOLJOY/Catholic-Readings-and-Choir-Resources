import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";

import { API_URL } from "@/config/api";

export const api = axios.create({
	baseURL: API_URL,
	timeout: 20000,
});

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

		const refreshToken = await AsyncStorage.getItem("refresh_token");
		if (!refreshToken) {
			await AsyncStorage.multiRemove(["access_token", "refresh_token", "user", "user_role"]);
			return Promise.reject(error);
		}

		request._retry = true;

		try {
			const response = await api.post("/api/auth/refresh", null, {
				params: { refresh_token: refreshToken },
			});
			const accessToken = response.data?.access_token;

			if (!accessToken) {
				throw new Error("Refresh response did not include an access token.");
			}

			await AsyncStorage.setItem("access_token", accessToken);
			if (response.data?.refresh_token) {
				await AsyncStorage.setItem("refresh_token", response.data.refresh_token);
			}
			request.headers = request.headers ?? {};
			request.headers.Authorization = `Bearer ${accessToken}`;
			return api(request);
		} catch (refreshError) {
			if (
				axios.isAxiosError(refreshError) &&
				refreshError.response &&
				[400, 401, 403].includes(refreshError.response.status)
			) {
				await AsyncStorage.multiRemove([
					"access_token",
					"refresh_token",
					"user",
					"user_role",
				]);
			}
			return Promise.reject(refreshError);
		}
	}
);
