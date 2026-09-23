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
