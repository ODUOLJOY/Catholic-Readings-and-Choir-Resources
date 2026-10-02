import { Stack, useRouter, useSegments } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Require a stored session for admin screens other than login.
 * Privilege checks remain on the backend and individual admin screens.
 */
export default function AdminLayout() {
  const router = useRouter();
  const segments = useSegments();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;

    async function guard() {
      const onLogin = segments[segments.length - 1] === "login";
      if (onLogin) {
        if (active) setReady(true);
        return;
      }

      const accessToken = await AsyncStorage.getItem("access_token");
      if (!accessToken) {
        router.replace("/(tabs)/admin/login");
        return;
      }

      if (active) setReady(true);
    }

    void guard();
    return () => {
      active = false;
    };
  }, [segments, router]);

  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color="#0B6623" />
      </View>
    );
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}
