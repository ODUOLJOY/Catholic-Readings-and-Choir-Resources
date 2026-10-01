import AsyncStorage from "@react-native-async-storage/async-storage";
import { api } from "@/lib/api";

export const authService = {
  async login(email: string, password: string) {
    const response = await api.post("/api/auth/login", {
      email: email.trim().toLowerCase(),
      password,
    });

    const { access_token, refresh_token } = response.data;

    await AsyncStorage.multiSet([
      ["access_token", access_token],
      ["refresh_token", refresh_token],
    ]);

    await this.fetchAndStoreUser();
    
    return response.data;
  },

  async fetchAndStoreUser() {
    const userResponse = await api.get("/api/auth/me");
    const user = userResponse.data;
    await this.storeUser(user);
    return user;
  },

  async storeUser<T extends { role?: unknown }>(user: T) {
    await AsyncStorage.multiSet([
      ["user", JSON.stringify(user)],
      ["user_role", String(user.role ?? "").toLowerCase()],
    ]);
  },

  async logout() {
    await AsyncStorage.multiRemove(["access_token", "refresh_token", "user", "user_role"]);
  },

  async getUser() {
    const user = await AsyncStorage.getItem("user");
    return user ? JSON.parse(user) : null;
  },

  async getRole() {
    return await AsyncStorage.getItem("user_role");
  },
};
