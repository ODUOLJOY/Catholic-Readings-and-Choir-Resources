import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="(auth)" />
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="profile" />
      <Stack.Screen name="settings" />
      <Stack.Screen name="downloads" />
      <Stack.Screen name="favorites" />
      <Stack.Screen name="search" />

      <Stack.Screen name="admin/dashboard" />
      <Stack.Screen name="admin/readings" />
      <Stack.Screen name="admin/upload" />
      <Stack.Screen name="admin/approve" />
      <Stack.Screen name="admin/saints" />
    </Stack>
  );
}