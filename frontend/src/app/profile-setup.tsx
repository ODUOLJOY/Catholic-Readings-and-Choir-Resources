import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";

import { api } from "@/lib/api";
import { authService } from "@/services/authService";
import { hierarchyService } from "@/services/hierarchyService";
import {
  EMPTY_SELECTION,
  HierarchyPicker,
  HierarchySelection,
} from "@/components/HierarchyPicker";

interface ApiError {
  message?: string;
  response?: { data?: { detail?: string } };
}

function errorMessage(error: unknown): string {
  const apiError = error as ApiError;
  return (
    apiError.response?.data?.detail ??
    apiError.message ??
    "Something went wrong. Please try again."
  );
}

export default function ProfileSetup() {
  const router = useRouter();
  const [selection, setSelection] = useState<HierarchySelection>(
    EMPTY_SELECTION
  );
  const [booting, setBooting] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-hydrate the cascade from the parish already stored on the account so the
  // saved location is shown rather than restarting at "Country".
  const initialize = useCallback(async () => {
    setBooting(true);
    setError(null);
    try {
      const response = await api.get<{ parish_id: number | null }>(
        "/api/v1/users/me/location"
      );
      const parishId = response.data?.parish_id;
      if (!parishId) return;

      const chain = await hierarchyService.resolveParish(parishId);
      setSelection({
        country: chain.country as HierarchySelection["country"],
        province: chain.province as HierarchySelection["province"],
        diocese: chain.diocese as HierarchySelection["diocese"],
        deanery: chain.deanery,
        parish: chain.parish as HierarchySelection["parish"],
      });
      setEditing(true);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setBooting(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(initialize);
  }, [initialize]);

  const submit = async () => {
    if (!selection.parish) {
      setError("Choose your parish before saving.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      // parish_id alone is enough: the server derives and validates the rest.
      const response = await api.put("/api/v1/users/me/location", {
        parish_id: selection.parish.id,
      });
      await authService.storeUser(response.data);
      router.replace("/(tabs)");
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  if (booting) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#0B6623" />
        <Text style={styles.muted}>Loading the Catholic directory…</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={styles.content}
      >
        <Text style={styles.eyebrow}>PARISH SETUP</Text>
        <Text style={styles.title}>
          {editing ? "Update your parish" : "Set up your parish"}
        </Text>
        <Text style={styles.description}>
          Walk down from your country to your parish.
        </Text>

        <HierarchyPicker
          initialSelection={selection}
          onChange={setSelection}
        />

        {error ? (
          <View accessibilityRole="alert" style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        <Pressable
          accessibilityRole="button"
          disabled={!selection.parish || saving}
          onPress={() => void submit()}
          style={[
            styles.submitButton,
            (!selection.parish || saving) && styles.disabled,
          ]}
        >
          {saving ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitText}>Save parish</Text>
          )}
        </Pressable>

        {editing ? (
          <Pressable
            accessibilityRole="button"
            onPress={() => router.replace("/(tabs)")}
            style={styles.cancelButton}
          >
            <Text style={styles.cancelText}>Cancel</Text>
          </Pressable>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20, paddingBottom: 36 },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  eyebrow: {
    color: "#0B6623",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.7,
    marginBottom: 10,
  },
  title: { color: "#17351f", fontSize: 27, fontWeight: "800" },
  description: { color: "#637067", fontSize: 14, marginTop: 8, marginBottom: 20 },
  errorBox: {
    backgroundColor: "#fff1f0",
    borderRadius: 10,
    padding: 12,
    marginTop: 12,
  },
  errorText: { color: "#982c20" },
  muted: { color: "#68736b" },
  submitButton: {
    backgroundColor: "#0B6623",
    borderRadius: 10,
    padding: 16,
    marginTop: 16,
    alignItems: "center",
  },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  disabled: { opacity: 0.5 },
  cancelButton: { alignItems: "center", padding: 14 },
  cancelText: { color: "#68736b", fontWeight: "600" },
});