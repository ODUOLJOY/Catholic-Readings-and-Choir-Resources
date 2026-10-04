import { Tabs, useRouter } from "expo-router";
import { FontAwesome5, Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { authService } from "@/services/authService";

export default function TabsLayout() {
  const router = useRouter();
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    async function checkSetup() {
      const user = await authService.getUser();
      const fetchedRole = await authService.getRole();
      setRole(fetchedRole ?? null);

      if (user && !user.profile_setup_completed) {
        router.replace("/profile-setup");
      }
    }
    void checkSetup();
  }, [router]);

  const isAdmin =
    role === "admin" ||
    role === "super_admin" ||
    role === "superadmin";

  // The Admin tab is only surfaced to users whose role grants administration
  // privileges. Privilege is also enforced server-side on every protected
  // endpoint; this is a UI affordance so non-administrators never see it.
  const visibleTabs = isAdmin
    ? ["index", "downloads", "choir", "profile", "admin"]
    : ["index", "downloads", "choir", "profile"];

  return (
    <Tabs
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarButton: visibleTabs.includes(route.name)
          ? undefined
          : () => null,
        tabBarActiveTintColor: "#0B6623",
        tabBarInactiveTintColor: "#777",
        tabBarStyle: {
          height: 68,
          paddingBottom: 8,
          paddingTop: 6,
          backgroundColor: "#ffffff",
          borderTopWidth: 1,
          borderTopColor: "#e5e5e5",
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: "600",
        },
      })}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="downloads"
        options={{
          title: "Downloads",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="cloud-download-outline" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="choir"
        options={{
          title: "Choir",
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="music-note" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size }) => (
            <FontAwesome5 name="user-circle" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="admin"
        options={{
          title: "Admin",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="shield-checkmark-outline" color={color} size={size} />
          ),
        }}
      />
    </Tabs>
  );
}
