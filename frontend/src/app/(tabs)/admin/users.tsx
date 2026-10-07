import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { api } from "@/lib/api";
import { requestErrorMessage } from "@/lib/requestFailure";

type User = {
  id: number;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
};

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);

  async function load() {
    try {
      setLoading(true);
      const response = await api.get<User[]>("/api/admin/users");
      setUsers(response.data);
    } catch (error: any) {
      Alert.alert(
        "Users unavailable",
        requestErrorMessage(error, "Unable to load users."),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void Promise.resolve().then(load);
  }, []);

  async function update(
    id: number,
    action: "enable" | "disable" | "delete",
    role?: string,
  ) {
    try {
      setBusy(id);
      if (action === "delete") {
        await api.delete(`/api/admin/users/${id}`);
      } else if (role) {
        await api.put(`/api/admin/users/${id}/role`, null, {
          params: { role },
        });
      } else {
        await api.put(`/api/admin/users/${id}/${action}`);
      }
      await load();
    } catch (error: any) {
      Alert.alert(
        "Update failed",
        requestErrorMessage(error, "Unable to update this user."),
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Manage Users</Text>
      {loading ? (
        <ActivityIndicator color="#0B6623" />
      ) : (
        <FlatList
          data={users}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Text style={styles.name}>{item.full_name}</Text>
              <Text style={styles.email}>{item.email}</Text>
              <Text style={styles.meta}>
                {item.role} · {item.is_active ? "Active" : "Disabled"}
              </Text>
              <View style={styles.actions}>
                <TouchableOpacity
                  onPress={() =>
                    update(item.id, item.is_active ? "disable" : "enable")
                  }
                  disabled={busy === item.id}
                >
                  <Text style={styles.action}>
                    {item.is_active ? "Disable" : "Enable"}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={() => update(item.id, "delete")}
                  disabled={busy === item.id}
                >
                  <Text style={styles.danger}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
          ListEmptyComponent={
            <Text style={styles.empty}>No users found.</Text>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 18,
    backgroundColor: "#fff",
  },
  title: {
    fontSize: 28,
    fontWeight: "800",
    color: "#0B6623",
    marginBottom: 15,
  },
  card: {
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 12,
    padding: 15,
    marginBottom: 10,
  },
  name: {
    fontSize: 17,
    fontWeight: "800",
  },
  email: {
    color: "#555",
    marginTop: 4,
  },
  meta: {
    color: "#777",
    marginTop: 5,
  },
  actions: {
    flexDirection: "row",
    gap: 18,
    marginTop: 12,
  },
  action: {
    color: "#0B6623",
    fontWeight: "800",
  },
  danger: {
    color: "#C62828",
    fontWeight: "800",
  },
  empty: {
    textAlign: "center",
    color: "#777",
    marginTop: 40,
  },
});
