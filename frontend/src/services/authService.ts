import AsyncStorage from "@react-native-async-storage/async-storage";
import { api } from "@/lib/api";

export const authService = {
  async login(email: string, password: string) {
    const response = await api.post("/api/auth/login", {
      email: email.trim().toLowerCase(),
      password,
    });

    await this.persistSession(response.data);

    return response.data;
  },

  async persistSession(data: {
    access_token?: string;
    refresh_token?: string;
  }) {
    const { access_token, refresh_token } = data;

    if (!access_token || !refresh_token) {
      throw new Error("The server did not return a complete session.");
    }

    await AsyncStorage.multiSet([
      ["access_token", access_token],
      ["refresh_token", refresh_token],
    ]);

    await this.fetchAndStoreUser();

    return data;
  },

  async restoreSession(): Promise<boolean> {
    const accessToken = await AsyncStorage.getItem("access_token");
    const refreshToken = await AsyncStorage.getItem("refresh_token");

    if (!accessToken && !refreshToken) {
      return false;
    }

    try {
      await this.fetchAndStoreUser();
      return true;
    } catch (error) {
      console.warn("Stored session could not be restored.", error);
      return false;
    }
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
    try {
      const refreshToken = await AsyncStorage.getItem("refresh_token");
      if (refreshToken) {
        await api.post("/api/auth/logout", { refresh_token: refreshToken });
      }
    } catch (error) {
      console.warn("Unable to revoke the server session; clearing local session.", error);
    } finally {
      await AsyncStorage.multiRemove(["access_token", "refresh_token", "user", "user_role"]);
    }
  },

  async logoutAll() {
    try {
      await api.post("/api/auth/logout-all");
    } catch (error) {
      console.warn("Unable to revoke server sessions; clearing local session.", error);
    } finally {
      await AsyncStorage.multiRemove(["access_token", "refresh_token", "user", "user_role"]);
    }
  },

  async getUser() {
    const user = await AsyncStorage.getItem("user");
    return user ? JSON.parse(user) : null;
  },

  async getRole() {
    return await AsyncStorage.getItem("user_role");
  },
};
