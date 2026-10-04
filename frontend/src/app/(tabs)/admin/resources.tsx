import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { api } from "@/lib/api";
import { CHOIR_CATEGORY_SECTIONS, canonicaliseCategory } from "@/config/choirCategories";

type Resource = {
  id: number;
  title: string;
  category: string;
  language: string;
  description?: string | null;
  is_approved?: boolean;
  is_published?: boolean;
  moderation_status?: string;
};

type ApiError = {
  response?: { data?: { detail?: string } };
  message?: string;
};

function errorMessage(error: unknown): string {
  const apiError = error as ApiError;
  return apiError.response?.data?.detail ?? apiError.message ?? "Unable to update resources.";
}

export default function AdminResources() {
  const [items, setItems] = useState<Resource[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<Resource | null>(null);
  const [rejectionTarget, setRejectionTarget] = useState<number | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [published, pending] = await Promise.all([
        api.get<Resource[]>("/api/choir/"),
        api.get<Resource[]>("/api/admin/pending-resources"),
      ]);
      const merged = [...(published.data ?? []), ...(pending.data ?? [])];
      setItems(Array.from(new Map(merged.map((item) => [item.id, item])).values()));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  async function moderate(id: number, action: "approve" | "reject" | "delete") {
    if (action === "reject") {
      setRejectionTarget(id);
      setRejectionReason("");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (action === "approve") {
        await api.put(`/api/admin/approve-resource/${id}`);
      } else {
        await api.delete(`/api/choir/${id}`);
      }
      await load();
    } catch (actionError) {
      setError(errorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  async function rejectResource() {
    if (rejectionTarget === null || !rejectionReason.trim()) {
      setError("Enter a reason before rejecting this resource.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await api.delete(`/api/admin/resources/${rejectionTarget}`, {
        params: { reason: rejectionReason.trim() },
      });
      setRejectionTarget(null);
      setRejectionReason("");
      await load();
    } catch (actionError) {
      setError(errorMessage(actionError));
    } finally {
      setSaving(false);
    }
  }

  function openEditor(item: Resource) {
    // If the stored category is a legacy label, normalise it to the canonical
    // equivalent so the selector shows an active chip and the save request
    // always sends a canonical value the backend will accept. Ambiguous labels
    // (canonicaliseCategory returns null) fall back to "Others" so the row is
    // never stuck on a label the backend would reject on save.
    const canonical = canonicaliseCategory(item.category) ?? "Others";
    setEditing({ ...item, category: canonical });
  }

  async function saveEdit() {
    if (!editing) return;

    setSaving(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("title", editing.title);
      form.append("category", editing.category);
      form.append("language", editing.language);
      form.append("description", editing.description ?? "");
      await api.put(`/api/choir/${editing.id}`, form);
      setEditing(null);
      await load();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#0B6623" />
      </View>
    );
  }

  if (editing) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Edit Resource</Text>
        <TextInput
          accessibilityLabel="Resource title"
          style={styles.input}
          value={editing.title}
          onChangeText={(value) => setEditing({ ...editing, title: value })}
        />
        <Text style={styles.fieldLabel}>Category</Text>
        <ScrollView style={styles.categoryScroll} showsVerticalScrollIndicator={false}>
          {CHOIR_CATEGORY_SECTIONS.map((section) => (
            <View key={section.title} style={styles.categorySection}>
              <Text style={styles.categorySectionTitle}>{section.title}</Text>
              <View style={styles.categoryRow}>
                {section.categories.map((item) => {
                  const active = editing.category === item;
                  return (
                    <Pressable
                      key={item}
                      disabled={saving}
                      style={[styles.chip, active && styles.chipActive]}
                      onPress={() => setEditing({ ...editing, category: item })}
                    >
                      <Text style={[styles.chipText, active && styles.chipTextActive]}>
                        {item}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ))}
        </ScrollView>
        <TextInput
          accessibilityLabel="Resource language"
          style={styles.input}
          value={editing.language}
          onChangeText={(value) => setEditing({ ...editing, language: value })}
        />
        <TextInput
          accessibilityLabel="Resource description"
          style={styles.area}
          multiline
          value={editing.description ?? ""}
          onChangeText={(value) => setEditing({ ...editing, description: value })}
        />
        {error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
        <Pressable
          accessibilityRole="button"
          disabled={saving}
          style={[styles.button, saving && styles.disabled]}
          onPress={() => void saveEdit()}
        >
          <Text style={styles.buttonText}>{saving ? "Saving…" : "Save Changes"}</Text>
        </Pressable>
        <Pressable disabled={saving} onPress={() => setEditing(null)}>
          <Text style={styles.cancel}>Cancel</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Manage Choir Resources</Text>
      {error && (
        <>
          <Text accessibilityRole="alert" style={styles.error}>{error}</Text>
          <Pressable onPress={() => void load()}>
            <Text style={styles.action}>Retry</Text>
          </Pressable>
        </>
      )}
      <FlatList
        data={items}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.heading}>{item.title}</Text>
            <Text style={styles.meta}>{item.category} · {item.language}</Text>
            <Text style={styles.meta}>
              {item.moderation_status ?? (item.is_approved ? "Approved" : "Pending approval")}
            </Text>
            <View style={styles.actions}>
              <Pressable disabled={saving} onPress={() => openEditor(item)}>
                <Text style={styles.action}>Edit</Text>
              </Pressable>
              {!item.is_approved && (
                <Pressable
                  disabled={saving}
                  onPress={() => void moderate(item.id, "approve")}
                >
                  <Text style={styles.action}>Approve</Text>
                </Pressable>
              )}
              <Pressable
                disabled={saving}
                onPress={() => void moderate(item.id, item.is_approved ? "delete" : "reject")}
              >
                <Text style={styles.danger}>{item.is_approved ? "Delete" : "Reject"}</Text>
              </Pressable>
            </View>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No resources found.</Text>}
      />
      <Modal
        animationType="fade"
        transparent
        visible={rejectionTarget !== null}
        onRequestClose={() => setRejectionTarget(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.heading}>Reject resource</Text>
            <Text style={styles.meta}>Give the uploader a clear reason for this decision.</Text>
            <TextInput
              accessibilityLabel="Rejection reason"
              editable={!saving}
              maxLength={1000}
              multiline
              onChangeText={setRejectionReason}
              placeholder="Reason for rejection"
              style={styles.area}
              value={rejectionReason}
            />
            {error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
            <View style={styles.actions}>
              <Pressable
                disabled={saving}
                onPress={() => {
                  setRejectionTarget(null);
                  setError(null);
                }}
              >
                <Text style={styles.action}>Cancel</Text>
              </Pressable>
              <Pressable disabled={saving} onPress={() => void rejectResource()}>
                <Text style={styles.danger}>{saving ? "Rejecting…" : "Reject resource"}</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 18, backgroundColor: "#fff" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623", marginBottom: 15 },
  card: { borderWidth: 1, borderColor: "#e5e5e5", borderRadius: 12, padding: 15, marginBottom: 10 },
  heading: { fontSize: 17, fontWeight: "800" },
  meta: { color: "#666", marginTop: 5 },
  actions: { flexDirection: "row", gap: 18, marginTop: 12 },
  action: { color: "#0B6623", fontWeight: "800" },
  danger: { color: "#C62828", fontWeight: "800" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 9, padding: 12, marginBottom: 10 },
  fieldLabel: { fontSize: 13, fontWeight: "700", color: "#333", marginBottom: 6, marginTop: 4 },
  categoryScroll: { maxHeight: 260, marginBottom: 10 },
  categorySection: { marginTop: 8 },
  categorySectionTitle: { fontSize: 12, fontWeight: "700", color: "#0B6623", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 6 },
  categoryRow: { flexDirection: "row", flexWrap: "wrap" },
  chip: { borderWidth: 1, borderColor: "#0B6623", borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: "#fff", marginRight: 7, marginBottom: 7 },
  chipActive: { backgroundColor: "#0B6623" },
  chipText: { color: "#0B6623", fontWeight: "700", fontSize: 12 },
  chipTextActive: { color: "#fff" },
  area: { borderWidth: 1, borderColor: "#ddd", borderRadius: 9, padding: 12, minHeight: 100, marginTop: 12, textAlignVertical: "top" },
  button: { backgroundColor: "#0B6623", padding: 14, borderRadius: 9, alignItems: "center" },
  buttonText: { color: "#fff", fontWeight: "800" },
  disabled: { opacity: 0.6 },
  cancel: { color: "#0B6623", fontWeight: "700", textAlign: "center", marginTop: 16 },
  empty: { color: "#777", textAlign: "center", marginTop: 40 },
  error: { color: "#982c20", backgroundColor: "#fff1f0", padding: 10, borderRadius: 8, marginBottom: 12 },
  modalBackdrop: { flex: 1, backgroundColor: "#0008", justifyContent: "center", padding: 20 },
  modalCard: { backgroundColor: "#fff", borderRadius: 12, padding: 18 },
});
