import { useState } from "react";
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
import { getList, saveList, StorageKeys } from "@/lib/storage";
import { api } from "@/lib/api";

const categories = [
  "Entrance",
  "Kyrie Eleison",
  "Gloria",
  "Responsorial Psalm",
  "Gospel Acclamation",
  "Sadaka",
  "Offertory",
  "Sanctus",
  "Memorial Acclamation",
  "Great Amen",
  "Agnus Dei",
  "Communion",
  "Thanksgiving",
  "Exit",
  "Recessional",
  "Advent",
  "Christmas",
  "Lent",
  "Holy Week",
  "Easter",
  "Pentecost",
  "Ordinary Time",
  "Marian",
  "Wedding",
  "Funeral",
  "Baptism",
  "Confirmation",
  "Ordination",
  "Other",
];

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

  async function pickFile() {
    try {
      const result =
        await DocumentPicker.getDocumentAsync({
          copyToCacheDirectory: true,
          multiple: false,
          type: "*/*",
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

    if (!content.trim() && !file) {
      Alert.alert(
        "Missing Content",
        "Enter reading content or attach a file."
      );
      return;
    }

    try {
      setUploading(true);

      const token =
        await AsyncStorage.getItem("access_token");

      const payload = {
        title: title.trim(),
        content: content.trim(),
        reference: reference.trim(),
        category,
        season,
        language,
        status: "pending",
        createdAt: new Date().toISOString(),
      };

      /*
       * Save a local copy first so the submission
       * isn't lost if the backend is temporarily offline.
       */
      const pending = await getList(
        StorageKeys.PENDING_READINGS
      );

      pending.unshift({
        id: Date.now().toString(),
        ...payload,
        fileName: file?.name ?? null,
        fileType: file?.mimeType ?? null,
        fileUri: file?.uri ?? null,
      });

      await saveList(
        StorageKeys.PENDING_READINGS,
        pending
      );

      /*
       * Send to backend when authenticated.
       */
      if (token && file) {
          const formData = new FormData();

          formData.append(
            "title",
            payload.title
          );
          formData.append(
            "description",
            payload.content
          );
          formData.append(
            "category",
            payload.category
          );
          formData.append(
            "language",
            payload.language
          );

          formData.append(
            "file",
            {
              uri: file.uri,
              name: file.name,
              type:
                file.mimeType ||
                "application/octet-stream",
            } as any
          );

          await api.post(
            "/api/uploads/",
            formData,
            {
              headers: { "Content-Type": "multipart/form-data" },
              timeout: 30000,
            }
          );
          Alert.alert(
            "Submitted for approval",
            "Your resource was uploaded and is waiting for administrator approval."
          );
      } else {
        Alert.alert(
          "Saved Locally",
          "Your resource was saved on this device and will require submission when you are authenticated."
        );
      }

      clearForm();
    } catch (error: any) {
      console.log(
        "Upload error:",
        error?.response?.data || error
      );

      Alert.alert(
        "Saved for Approval",
        "The resource was saved locally, but the server could not be reached."
      );

      clearForm();
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
              Submit Reading
            </Text>

            <Text style={styles.subtitle}>
              Submit Catholic content for approval
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
          Bible Reference
        </Text>

        <TextInput
          style={styles.input}
          placeholder="e.g. John 6:35-40"
          placeholderTextColor="#999"
          value={reference}
          onChangeText={setReference}
          editable={!uploading}
        />

        <Text style={styles.label}>
          Category
        </Text>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.horizontal}
        >
          {categories.map((item) => (
            <Pressable
              key={item}
              style={[
                styles.chip,
                category === item &&
                  styles.chipActive,
              ]}
              onPress={() =>
                setCategory(item)
              }
              disabled={uploading}
            >
              <Text
                style={[
                  styles.chipText,
                  category === item &&
                    styles.chipTextActive,
                ]}
              >
                {item}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

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
          Reading Content
        </Text>

        <TextInput
          style={styles.textArea}
          placeholder="Enter the reading content..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={content}
          onChangeText={setContent}
          editable={!uploading}
        />

        <Text style={styles.label}>
          Optional File
        </Text>

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

        <View style={styles.notice}>
          <Ionicons
            name="information-circle-outline"
            size={20}
            color="#0B6623"
          />

          <Text style={styles.noticeText}>
            Submitted resources remain pending until
            an administrator reviews and approves
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
          disabled={uploading}
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

  chip: {
    borderWidth: 1,
    borderColor: "#0B6623",
    borderRadius: 20,
    paddingHorizontal: 13,
    paddingVertical: 8,
    backgroundColor: "#fff",
    marginRight: 8,
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