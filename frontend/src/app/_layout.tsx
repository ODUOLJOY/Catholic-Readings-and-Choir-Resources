import { useEffect, useState } from "react";
import { Stack, useRouter, useSegments } from "expo-router";

import { authService } from "@/services/authService";

export default function RootLayout() {
  const [authenticated, setAuthenticated] = useState(false);
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    let active = true;

    authService.restoreSession().then((restored) => {
      if (active) setAuthenticated(restored);
    });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const inAuthGroup = segments[0] === "(auth)";
    if (authenticated && inAuthGroup) {
      router.replace("/(tabs)");
    }
  }, [authenticated, segments, router]);

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
