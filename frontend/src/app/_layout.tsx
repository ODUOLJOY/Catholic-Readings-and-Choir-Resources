import { useEffect, useState } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { authService } from "@/services/authService";
import { onSessionChange } from "@/lib/api";
import { ChoirPlayerProvider } from "@/components/choir/ChoirPlayerProvider";

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

  // A refresh that fails server-side clears the stored session. Reflect that here
  // so the app stops presenting itself as signed in instead of leaving every
  // screen showing whatever error the next request happened to produce.
  useEffect(
    () => onSessionChange((sessionActive) => setAuthenticated(sessionActive)),
    [],
  );

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
    // The choir player is mounted here so an active resource survives
    // navigation between the library and a detail page. It renders nothing when
    // no choir resource is active.
    <ChoirPlayerProvider>
      <Stack
        screenOptions={{
          headerShown: false,
          animation: "slide_from_right",
        }}
      >
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="reading-detail" />
        <Stack.Screen name="missal" />
      </Stack>
    </ChoirPlayerProvider>
  );
}
