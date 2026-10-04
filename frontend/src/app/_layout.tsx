import { useEffect, useState } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { authService } from "@/services/authService";

export default function RootLayout() {
  const [authenticated, setAuthenticated] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    let active = true;

    authService.restoreSession().then((restored) => {
      if (active) {
        setAuthenticated(restored);
        // Auth state is now resolved — never navigate before this point.
        setRestoring(false);
      }
    });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const inAuthGroup = segments[0] === "(auth)";
    // Only redirect when auth state is known. Public screens (readings, choir,
    // etc.) remain reachable without a session; privilege checks live server-side.
    if (!restoring && authenticated && inAuthGroup) {
      router.replace("/(tabs)");
    }
  }, [authenticated, restoring, segments, router]);

  if (restoring) {
    return (
      <View
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#ffffff",
        }}
      >
        <ActivityIndicator size="large" color="#0B6623" />
      </View>
    );
  }

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: "slide_from_right",
      }}
    >
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="reading-detail" />
    </Stack>
  );
}
