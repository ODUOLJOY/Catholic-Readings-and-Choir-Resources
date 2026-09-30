import { Tabs } from "expo-router";
import { Ionicons, FontAwesome5 } from "@expo/vector-icons";

export default function TabsLayout() {
  const visibleTabs = new Set(["index", "profile", "admin", "readings", "payment", "downloads"]);

  return (
    <Tabs
      screenOptions={({ route }) => ({
        headerShown: false,
        href: visibleTabs.has(route.name) ? undefined : null,

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
      {/* HOME */}
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="home-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      {/* ADMIN */}
      <Tabs.Screen
        name="admin"
        options={{
          title: "Admin",
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="shield-checkmark-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      {/* PROFILE */}
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size }) => (
            <FontAwesome5
              name="user-circle"
              color={color}
              size={size}
            />
          ),
        }}
      />

      {/* PAYMENTS */}
      <Tabs.Screen
        name="payment"
        options={{
          title: "Payments",
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="card-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      {/* READINGS */}
      <Tabs.Screen
        name="readings"
        options={{
          title: "Readings",
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="book-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      {/* DOWNLOADS */}
      <Tabs.Screen
        name="downloads"
        options={{
          title: "Downloads",
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="cloud-download-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

    </Tabs>
  );
}