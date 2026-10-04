import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { api } from "@/lib/api";
import { CHOIR_CATEGORY_SECTIONS } from "@/config/choirCategories";

// Canonical 27 categories imported from @/config/choirCategories so the
// upload selector stays in sync with the browse screen and the edit screen.

const seasons = [
  "Advent",
  "Christmas",
  "Ordinary Time",
  "Lent",
  "Holy Week",
  "Triduum",
  "Easter",
  "Pentecost",
];

export default function UploadScreen() {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [reference, setReference] = useState("");
  const [category, setCategory] = useState(
    "Responsorial Psalm"
  );
  const [season, setSeason] = useState(
    "Ordinary Time"
  );
  const [language, setLanguage] = useState(
    "English"
  );
  const [file, setFile] =
    useState<DocumentPicker.DocumentPickerAsset | null>(
      null
    );

  const [uploading, setUploading] = useState(false);
  const [parishes, setParishes] = useState<{ id: number; name: string }[]>([]);
  const [parishId, setParishId] = useState<number | null>(null);
  const [globalScopeAllowed, setGlobalScopeAllowed] = useState(false);
  const [globalScope, setGlobalScope] = useState(false);
  const [scopeLoading, setScopeLoading] = useState(true);
  const [scopeLoadError, setScopeLoadError] = useState<string | null>(null);

  useEffect(() => {
    async function loadUploadScopes() {
      if (!(await AsyncStorage.getItem("access_token"))) {
        setScopeLoadError("Sign in before submitting a resource.");
        setScopeLoading(false);
        return;
      }
      try {
        const response = await api.get<{
          parishes: { id: number; name: string }[];
          global_scope_allowed: boolean;
        }>(
          "/api/uploads/scopes"
        );
        setParishes(response.data.parishes);
        setGlobalScopeAllowed(response.data.global_scope_allowed);
        if (response.data.global_scope_allowed) {
          setGlobalScope(true);
        } else if (response.data.parishes.length === 1) {
          setParishId(response.data.parishes[0].id);
        }
      } catch (error: any) {
        setScopeLoadError(
          error?.response?.data?.detail ||
            "Your upload permissions could not be loaded. Retry after checking your connection."
        );
      } finally {
        setScopeLoading(false);
      }
    }

    void loadUploadScopes();
  }, []);

  async function pickFile() {
    try {
      const result =
        await DocumentPicker.getDocumentAsync({
          copyToCacheDirectory: true,
          multiple: false,
          type: ["application/pdf", "image/*", "audio/*", "video/*"],
        });

      if (!result.canceled) {
        setFile(result.assets[0]);
      }
    } catch {
      Alert.alert(
        "Error",
        "Unable to select the file."
      );
    }
  }

  async function upload() {
    if (!title.trim()) {
      Alert.alert(
        "Missing Title",
        "Enter a title for the reading."
      );
      return;
    }

    if (!file) {
      Alert.alert(
        "File Required",
        "Choose a PDF, audio, video, or image file to upload."
      );
      return;
    }

    if (scopeLoading) {
      Alert.alert("Please wait", "Your authorized upload scopes are still loading.");
      return;
    }
    if (!globalScope && parishId === null) {
      Alert.alert(
        "Choose a Resource Scope",
        "Select one of your authorized parishes before submitting."
      );
      return;
    }
    if (globalScope && !globalScopeAllowed) {
      Alert.alert(
        "Global Upload Not Allowed",
        "Only platform administrators can submit global resources."
      );
      return;
    }

    try {
      setUploading(true);

      const token =
        await AsyncStorage.getItem("access_token");

      if (!token) {
        Alert.alert(
          "Authentication Required",
          "Please log in before uploading a resource."
        );
        return;
      }

      const formData = new FormData();
      formData.append("title", title.trim());
      const description = [
        content.trim(),
        reference.trim() ? `Bible reference: ${reference.trim()}` : "",
        `Liturgical season: ${season}`,
      ]
        .filter(Boolean)
        .join("\n\n");
      formData.append("description", description);
      formData.append("category", category);
      formData.append("language", language);
      formData.append("global_scope", String(globalScope));
      if (parishId !== null) {
        formData.append("parish_id", String(parishId));
      }
      if (Platform.OS === "web") {
        const selectedFile = await fetch(file.uri).then((response) => {
          if (!response.ok) {
            throw new Error("Unable to read the selected file.");
          }
          return response.blob();
        });
        formData.append("file", selectedFile, file.name);
      } else {
        const nativeFormData = formData as FormData & {
          append(
            name: string,
            value: { uri: string; name: string; type: string }
          ): void;
        };
        nativeFormData.append("file", {
          uri: file.uri,
          name: file.name,
          type: file.mimeType || "application/octet-stream",
        });
      }

      await api.post("/api/uploads/", formData, {
        timeout: 600000,
      });

      Alert.alert(
        "Submitted for approval",
        "Your resource was uploaded and is waiting for an authorized reviewer."
      );

      clearForm();
    } catch (error: any) {
      Alert.alert(
        "Upload Failed",
        error?.response?.data?.detail ||
          "The resource could not be uploaded. Please try again."
      );
    } finally {
      setUploading(false);
    }
  }

  function clearForm() {
    setTitle("");
    setContent("");
    setReference("");
    setCategory("Responsorial Psalm");
    setSeason("Ordinary Time");
    setLanguage("English");
    setFile(null);
    setGlobalScope(globalScopeAllowed);
    setParishId(
      !globalScopeAllowed && parishes.length === 1
        ? parishes[0].id
        : null
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={
        Platform.OS === "ios"
          ? "padding"
          : undefined
      }
    >
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <View style={styles.headerIcon}>
            <MaterialCommunityIcons
              name="cloud-upload"
              size={29}
              color="#0B6623"
            />
          </View>

          <View style={styles.headerText}>
            <Text style={styles.title}>
                Submit Choir Resource
            </Text>

            <Text style={styles.subtitle}>
              Submit audio, video, PDF or sheet music for approval
            </Text>
          </View>
        </View>

        <Text style={styles.label}>
          Title
        </Text>

        <TextInput
          style={styles.input}
          placeholder="Reading or resource title"
          placeholderTextColor="#999"
          value={title}
          onChangeText={setTitle}
          editable={!uploading}
        />

        <Text style={styles.label}>
          Resource Reference
        </Text>

        <TextInput
          style={styles.input}
          placeholder="e.g. composer, source, or Bible reference"
          placeholderTextColor="#999"
          value={reference}
          onChangeText={setReference}
          editable={!uploading}
        />

        <Text style={styles.label}>
          Category
        </Text>

        <View style={styles.categorySections}>
          {CHOIR_CATEGORY_SECTIONS.map((section) => (
            <View key={section.title} style={styles.categorySection}>
              <Text style={styles.categorySectionTitle}>
                {section.title}
              </Text>
              <View style={styles.categoryRow}>
                {section.categories.map((item) => {
                  const active = category === item;
                  return (
                    <Pressable
                      key={item}
                      style={[
                        styles.chip,
                        active && styles.chipActive,
                      ]}
                      onPress={() => setCategory(item)}
                      disabled={uploading}
                    >
                      <Text
                        style={[
                          styles.chipText,
                          active && styles.chipTextActive,
                        ]}
                      >
                        {item}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ))}
        </View>

        <Text style={styles.label}>
          Liturgical Season
        </Text>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.horizontal}
        >
          {seasons.map((item) => (
            <Pressable
              key={item}
              style={[
                styles.chip,
                season === item &&
                  styles.chipActive,
              ]}
              onPress={() =>
                setSeason(item)
              }
              disabled={uploading}
            >
              <Text
                style={[
                  styles.chipText,
                  season === item &&
                    styles.chipTextActive,
                ]}
              >
                {item}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        <Text style={styles.label}>
          Language
        </Text>

        <View style={styles.languageRow}>
          {["English", "Swahili", "Latin"].map(
            (item) => (
              <Pressable
                key={item}
                style={[
                  styles.languageChip,
                  language === item &&
                    styles.chipActive,
                ]}
                onPress={() =>
                  setLanguage(item)
                }
                disabled={uploading}
              >
                <Text
                  style={[
                    styles.chipText,
                    language === item &&
                      styles.chipTextActive,
                  ]}
                >
                  {item}
                </Text>
              </Pressable>
            )
          )}
        </View>

        <Text style={styles.label}>
          Resource Notes or Lyrics
        </Text>

        <TextInput
          style={styles.textArea}
          placeholder="Add helpful notes or lyrics (optional)..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={content}
          onChangeText={setContent}
          editable={!uploading}
        />

        <Text style={styles.label}>File (required)</Text>

        <Pressable
          style={styles.fileButton}
          onPress={pickFile}
          disabled={uploading}
        >
          <Ionicons
            name="document-attach-outline"
            size={22}
            color="#0B6623"
          />

          <View style={styles.fileTextContainer}>
            <Text style={styles.fileTitle}>
              {file
                ? file.name
                : "Attach PDF, audio, video or other file"}
            </Text>

            {file?.size ? (
              <Text style={styles.fileSize}>
                {(file.size / 1024 / 1024).toFixed(
                  2
                )}{" "}
                MB
              </Text>
            ) : null}
          </View>

          <Ionicons
            name="chevron-forward"
            size={19}
            color="#999"
          />
        </Pressable>

        {globalScopeAllowed || parishes.length > 0 ? (
          <>
            <Text style={styles.label}>Resource Scope</Text>
            <View style={styles.scopeRow}>
              {globalScopeAllowed ? (
                <Pressable
                  style={[
                    styles.languageChip,
                    globalScope && styles.chipActive,
                  ]}
                  onPress={() => {
                    setGlobalScope(true);
                    setParishId(null);
                  }}
                  disabled={uploading}
                >
                  <Text
                    style={[
                      styles.chipText,
                      globalScope && styles.chipTextActive,
                    ]}
                  >
                    Global
                  </Text>
                </Pressable>
              ) : null}
              {parishes.map((parish) => (
                <Pressable
                  key={parish.id}
                  style={[
                    styles.languageChip,
                    !globalScope && parishId === parish.id && styles.chipActive,
                  ]}
                  onPress={() => {
                    setGlobalScope(false);
                    setParishId(parish.id);
                  }}
                  disabled={uploading}
                >
                  <Text
                    style={[
                      styles.chipText,
                      !globalScope && parishId === parish.id && styles.chipTextActive,
                    ]}
                  >
                    {parish.name}
                  </Text>
                </Pressable>
              ))}
            </View>
          </>
        ) : null}
        {scopeLoadError ? (
          <Text style={styles.scopeError}>{scopeLoadError}</Text>
        ) : null}
        {!scopeLoading && !globalScopeAllowed && parishes.length === 0 && !scopeLoadError ? (
          <Text style={styles.scopeError}>
            No parish upload permissions are assigned to your account.
          </Text>
        ) : null}

        <View style={styles.notice}>
          <Ionicons
            name="information-circle-outline"
            size={20}
            color="#0B6623"
          />

          <Text style={styles.noticeText}>
            Submitted files stay private until an
            authorized parish or platform reviewer approves
            them.
          </Text>
        </View>

        <Pressable
          style={[
            styles.submitButton,
            uploading &&
              styles.submitButtonDisabled,
          ]}
          onPress={upload}
          disabled={uploading || scopeLoading}
        >
          {uploading ? (
            <View style={styles.submitContent}>
              <ActivityIndicator color="#fff" />

              <Text style={styles.submitText}>
                Submitting...
              </Text>
            </View>
          ) : (
            <View style={styles.submitContent}>
              <Ionicons
                name="cloud-upload-outline"
                size={21}
                color="#fff"
              />

              <Text style={styles.submitText}>
                Submit for Approval
              </Text>
            </View>
          )}
        </Pressable>

        <Text style={styles.footer}>
          Catholic Readings & Choir Resources
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#F7F9F7",
  },

  container: {
    flex: 1,
  },

  content: {
    padding: 18,
    paddingBottom: 40,
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 25,
  },

  headerIcon: {
    width: 54,
    height: 54,
    borderRadius: 16,
    backgroundColor: "#EAF4ED",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },

  headerText: {
    flex: 1,
  },

  title: {
    fontSize: 28,
    fontWeight: "800",
    color: "#0B6623",
  },

  subtitle: {
    color: "#777",
    fontSize: 13,
    marginTop: 3,
  },

  label: {
    fontSize: 14,
    fontWeight: "700",
    color: "#333",
    marginBottom: 7,
    marginTop: 5,
  },

  input: {
    minHeight: 52,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D9DED9",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: "#222",
    fontSize: 15,
    marginBottom: 13,
  },

  textArea: {
    minHeight: 190,
    textAlignVertical: "top",
  },

  horizontal: {
    marginBottom: 12,
  },

  categorySections: {
    marginBottom: 4,
  },

  categorySection: {
    marginTop: 10,
  },

  categorySectionTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0B6623",
    textTransform: "uppercase",
    letterSpacing: 0.4,
    marginBottom: 8,
  },

  categoryRow: {
    flexDirection: "row",
    flexWrap: "wrap",
  },

  chip: {
    borderWidth: 1,
    borderColor: "#0B6623",
    borderRadius: 20,
    paddingHorizontal: 13,
    paddingVertical: 8,
    backgroundColor: "#fff",
    marginRight: 8,
    marginBottom: 8,
  },

  chipActive: {
    backgroundColor: "#0B6623",
  },

  chipText: {
    color: "#0B6623",
    fontWeight: "700",
    fontSize: 12,
  },

  chipTextActive: {
    color: "#fff",
  },

  languageRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 8,
  },
  scopeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 12,
  },
  scopeError: {
    color: "#A32626",
    fontSize: 13,
    marginBottom: 12,
  },

  languageChip: {
    borderWidth: 1,
    borderColor: "#0B6623",
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 9,
    backgroundColor: "#fff",
    marginRight: 8,
    marginBottom: 8,
  },

  fileButton: {
    minHeight: 62,
    backgroundColor: "#fff",
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "#D9DED9",
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 15,
  },

  fileTextContainer: {
    flex: 1,
    marginHorizontal: 11,
  },

  fileTitle: {
    color: "#333",
    fontWeight: "700",
    fontSize: 14,
  },

  fileSize: {
    color: "#888",
    fontSize: 12,
    marginTop: 3,
  },

  notice: {
    backgroundColor: "#EAF4ED",
    borderRadius: 12,
    padding: 13,
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 18,
  },

  noticeText: {
    flex: 1,
    color: "#45634D",
    fontSize: 12,
    lineHeight: 18,
    marginLeft: 8,
  },

  submitButton: {
    minHeight: 55,
    backgroundColor: "#0B6623",
    borderRadius: 13,
    justifyContent: "center",
    alignItems: "center",
  },

  submitButtonDisabled: {
    opacity: 0.7,
  },

  submitContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
  },

  submitText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "800",
  },

  footer: {
    color: "#aaa",
    fontSize: 11,
    textAlign: "center",
    marginTop: 20,
  },
});