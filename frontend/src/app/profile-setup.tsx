import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useRouter } from "expo-router";

import { api } from "@/lib/api";
import { authService } from "@/services/authService";

interface DirectoryOption {
  id: number;
  name: string;
}

type SetupStep = "diocese" | "deanery" | "parish";

interface SavedLocation {
  diocese_id: number | null;
  deanery_id: number | null;
  parish_id: number | null;
}

interface ApiError {
  message?: string;
  response?: { data?: { detail?: string } };
}

function errorMessage(error: unknown): string {
  const apiError = error as ApiError;
  return apiError.response?.data?.detail ?? apiError.message ?? "Something went wrong. Please try again.";
}

export default function ProfileSetup() {
  const router = useRouter();
  const [step, setStep] = useState<SetupStep>("diocese");
  const [dioceses, setDioceses] = useState<DirectoryOption[]>([]);
  const [deaneries, setDeaneries] = useState<DirectoryOption[]>([]);
  const [parishes, setParishes] = useState<DirectoryOption[]>([]);
  const [selectedDiocese, setSelectedDiocese] = useState<DirectoryOption | null>(null);
  const [selectedDeanery, setSelectedDeanery] = useState<DirectoryOption | null>(null);
  const [selectedParish, setSelectedParish] = useState<DirectoryOption | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initialize = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dioceseResponse, locationResponse] = await Promise.all([
        api.get<DirectoryOption[]>("/api/v1/locations/dioceses"),
        api.get<SavedLocation>("/api/v1/users/me/location"),
      ]);
      const availableDioceses = dioceseResponse.data;
      if (!Array.isArray(availableDioceses)) {
        throw new Error("The directory returned an invalid Diocese list.");
      }
      setDioceses(availableDioceses);

      const saved: SavedLocation = locationResponse.data;
      const diocese = availableDioceses.find((item) => item.id === saved.diocese_id);
      if (!diocese || !saved.deanery_id || !saved.parish_id) return;

      const deaneryResponse = await api.get<DirectoryOption[]>(
        `/api/v1/locations/dioceses/${diocese.id}/deaneries`,
      );
      const availableDeaneries = deaneryResponse.data;
      const deanery = availableDeaneries.find((item) => item.id === saved.deanery_id);
      if (!deanery) return;

      const parishResponse = await api.get<DirectoryOption[]>(
        `/api/v1/locations/deaneries/${deanery.id}/parishes`,
      );
      const availableParishes = parishResponse.data;
      const parish = availableParishes.find((item) => item.id === saved.parish_id);
      if (!parish) return;

      setSelectedDiocese(diocese);
      setSelectedDeanery(deanery);
      setSelectedParish(parish);
      setDeaneries(availableDeaneries);
      setParishes(availableParishes);
      setStep("parish");
      setEditing(true);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(initialize);
  }, [initialize]);

  const options = step === "diocese" ? dioceses : step === "deanery" ? deaneries : parishes;
  const visibleOptions = useMemo(
    () => options.filter((item) => item.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())),
    [options, search],
  );
  const stepTitle = step === "diocese" ? "Choose your Diocese" : step === "deanery" ? "Choose your Deanery" : "Choose your Parish";
  const stepNumber = step === "diocese" ? 1 : step === "deanery" ? 2 : 3;

  const selectDiocese = async (diocese: DirectoryOption) => {
    setSelectedDiocese(diocese);
    setSelectedDeanery(null);
    setSelectedParish(null);
    setDeaneries([]);
    setParishes([]);
    setSearch("");
    setError(null);
    setLoading(true);
    try {
      const response = await api.get<DirectoryOption[]>(
        `/api/v1/locations/dioceses/${diocese.id}/deaneries`,
      );
      if (!Array.isArray(response.data)) throw new Error("The directory returned an invalid Deanery list.");
      setDeaneries(response.data);
      setStep("deanery");
      if (response.data.length === 0) setError("No active Deaneries are listed for this Diocese yet.");
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  };

  const selectDeanery = async (deanery: DirectoryOption) => {
    setSelectedDeanery(deanery);
    setSelectedParish(null);
    setParishes([]);
    setSearch("");
    setError(null);
    setLoading(true);
    try {
      const response = await api.get<DirectoryOption[]>(
        `/api/v1/locations/deaneries/${deanery.id}/parishes`,
      );
      if (!Array.isArray(response.data)) throw new Error("The directory returned an invalid Parish list.");
      setParishes(response.data);
      setStep("parish");
      if (response.data.length === 0) setError("No active Parishes are listed for this Deanery yet.");
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  };

  const retry = () => {
    if (step === "diocese") {
      void initialize();
      return;
    }
    if (step === "deanery" && selectedDiocese) {
      void selectDiocese(selectedDiocese);
      return;
    }
    if (step === "parish" && selectedDeanery) void selectDeanery(selectedDeanery);
  };

  const submit = async () => {
    if (!selectedDiocese || !selectedDeanery || !selectedParish) {
      setError("Choose a Diocese, Deanery and Parish before saving.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const response = await api.put("/api/v1/users/me/location", {
        parish_id: selectedParish.id,
        deanery_id: selectedDeanery.id,
        diocese_id: selectedDiocese.id,
      });
      await authService.storeUser(response.data);
      router.replace("/(tabs)");
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  if (loading && dioceses.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#0B6623" />
        <Text style={styles.muted}>Loading the Catholic directory…</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>PROFILE SETUP · STEP {stepNumber} OF 3</Text>
        <Text style={styles.title}>{editing ? "Update your parish" : "Set up your parish"}</Text>
        <Text style={styles.description}>
          {selectedDiocese?.name ?? "Diocese"}
          {selectedDeanery ? `  ›  ${selectedDeanery.name}` : ""}
          {selectedParish ? `  ›  ${selectedParish.name}` : ""}
        </Text>

        {step !== "diocese" && (
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              setError(null);
              setSearch("");
              setStep(step === "parish" ? "deanery" : "diocese");
            }}
            style={styles.backButton}
          >
            <Text style={styles.backText}>‹  Back</Text>
          </Pressable>
        )}

        <Text style={styles.sectionTitle}>{stepTitle}</Text>
        <TextInput
          accessibilityLabel={`Search ${stepTitle}`}
          autoCapitalize="none"
          onChangeText={setSearch}
          placeholder={`Search ${step === "diocese" ? "Dioceses" : step === "deanery" ? "Deaneries" : "Parishes"}`}
          style={styles.search}
          value={search}
        />

        {error && (
          <View accessibilityRole="alert" style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={retry} accessibilityRole="button">
              <Text style={styles.retry}>Try again</Text>
            </Pressable>
          </View>
        )}

        {loading ? (
          <ActivityIndicator style={styles.loader} color="#0B6623" />
        ) : visibleOptions.length ? (
          visibleOptions.map((item) => {
            const selected = step === "parish" && selectedParish?.id === item.id;
            return (
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ selected }}
                key={item.id}
                onPress={() => {
                  if (step === "diocese") void selectDiocese(item);
                  else if (step === "deanery") void selectDeanery(item);
                  else setSelectedParish(item);
                }}
                style={[styles.option, selected && styles.optionSelected]}
              >
                <Text style={[styles.optionText, selected && styles.optionTextSelected]}>{item.name}</Text>
                {selected && <Text style={styles.check}>Selected</Text>}
              </Pressable>
            );
          })
        ) : (
          <Text style={styles.empty}>
            {search ? "No matches. Try another search." : "No directory entries are available at this step."}
          </Text>
        )}

        {step === "parish" && (
          <Pressable
            accessibilityRole="button"
            disabled={!selectedParish || saving}
            onPress={() => void submit()}
            style={[styles.submitButton, (!selectedParish || saving) && styles.disabled]}
          >
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Save parish</Text>}
          </Pressable>
        )}

        {editing && (
          <Pressable accessibilityRole="button" onPress={() => router.replace("/(tabs)")} style={styles.cancelButton}>
            <Text style={styles.cancelText}>Cancel</Text>
          </Pressable>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20, paddingBottom: 36 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  eyebrow: { color: "#0B6623", fontSize: 12, fontWeight: "700", letterSpacing: 0.7, marginBottom: 10 },
  title: { color: "#17351f", fontSize: 27, fontWeight: "800" },
  description: { color: "#637067", fontSize: 14, marginTop: 8, marginBottom: 20 },
  sectionTitle: { color: "#1d2b21", fontSize: 18, fontWeight: "700", marginBottom: 10 },
  search: { borderColor: "#d8e0da", borderWidth: 1, borderRadius: 10, padding: 13, marginBottom: 14 },
  option: { padding: 15, backgroundColor: "#f4f7f4", marginBottom: 9, borderRadius: 10, borderWidth: 1, borderColor: "#edf0ed" },
  optionSelected: { backgroundColor: "#e7f3e9", borderColor: "#0B6623" },
  optionText: { color: "#26332a", fontSize: 16 },
  optionTextSelected: { color: "#0B6623", fontWeight: "700" },
  check: { color: "#0B6623", fontSize: 12, fontWeight: "700", marginTop: 4 },
  backButton: { alignSelf: "flex-start", paddingVertical: 10, marginBottom: 12 },
  backText: { color: "#0B6623", fontSize: 15, fontWeight: "700" },
  errorBox: { backgroundColor: "#fff1f0", borderRadius: 10, padding: 12, marginBottom: 12 },
  errorText: { color: "#982c20" },
  retry: { color: "#0B6623", fontWeight: "700", marginTop: 8 },
  loader: { marginVertical: 24 },
  empty: { color: "#68736b", textAlign: "center", padding: 18 },
  muted: { color: "#68736b" },
  submitButton: { backgroundColor: "#0B6623", borderRadius: 10, padding: 16, marginTop: 16, alignItems: "center" },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  disabled: { opacity: 0.5 },
  cancelButton: { alignItems: "center", padding: 14 },
  cancelText: { color: "#68736b", fontWeight: "600" },
});
