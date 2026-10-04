import { Platform } from "react-native";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";

import { api } from "@/lib/api";
import { authService } from "@/services/authService";

export function googleRedirectUri(): string {
  if (
    Platform.OS === "web" &&
    typeof window !== "undefined" &&
    window.location?.origin
  ) {
    return `${window.location.origin}/auth/google`;
  }

  return Linking.createURL("auth/google");
}

export const googleAuthService = {
  async isEnabled(): Promise<boolean> {
    try {
      const response = await api.get("/api/auth/google/config");
      return Boolean(response.data?.enabled);
    } catch {
      return false;
    }
  },

  async signIn(): Promise<void> {
    const redirectUri = googleRedirectUri();

    const config = await api.get("/api/auth/google/authorization-url", {
      params: { redirect_uri: redirectUri },
    });
    const authorizationUrl: string | undefined = config.data?.authorization_url;
    const state: string | undefined = config.data?.state;

    if (!authorizationUrl || !state) {
      throw new Error("Google sign-in is not available right now.");
    }

    const result = await WebBrowser.openAuthSessionAsync(
      authorizationUrl,
      redirectUri,
    );

    if (result.type !== "success" || !result.url) {
      throw new Error("Google sign-in was cancelled.");
    }

    const parsed = Linking.parse(result.url);
    const params = (parsed.queryParams ?? {}) as Record<
      string,
      string | string[] | undefined
    >;
    const value = (key: string) => {
      const entry = params[key];
      return Array.isArray(entry) ? entry[0] : entry;
    };

    if (value("error")) {
      throw new Error("Google sign-in was denied.");
    }

    const code = value("code");
    const returnedState = value("state");

    if (!code) {
      throw new Error("Google did not return an authorization code.");
    }

    if (returnedState !== state) {
      throw new Error("Google sign-in security check failed.");
    }

    const response = await api.post("/api/auth/google/callback", {
      code,
      redirect_uri: redirectUri,
      state,
    });

    await authService.persistSession(response.data);

    // No fabricated "created" flag: account creation vs. linking is resolved
    // server-side by login_with_google_identity (Google subject + email), and
    // post-sign-in navigation is driven by the user's profile_setup_completed
    // flag fetched from /api/auth/me. Returning { created: true } here would
    // falsely claim every Google sign-in created a new account.
  },
};
