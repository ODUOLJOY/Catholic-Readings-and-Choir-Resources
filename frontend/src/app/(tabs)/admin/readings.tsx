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
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";
import { api } from "@/lib/api";

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

export default function AdminReadings() {
  const [title, setTitle] = useState("");
  const [readingDate, setReadingDate] = useState("");
  const [liturgicalYear, setLiturgicalYear] = useState("A");
  const [season, setSeason] = useState("Ordinary Time");
  const [feast, setFeast] = useState("");
  const [saint, setSaint] = useState("");

  const [firstReference, setFirstReference] = useState("");
  const [firstReading, setFirstReading] = useState("");

  const [psalmReference, setPsalmReference] = useState("");
  const [psalm, setPsalm] = useState("");
  const [psalmResponse, setPsalmResponse] = useState("");

  const [secondReference, setSecondReference] = useState("");
  const [secondReading, setSecondReading] = useState("");

  const [gospelAcclamation, setGospelAcclamation] =
    useState("");

  const [gospelReference, setGospelReference] =
    useState("");
  const [gospel, setGospel] = useState("");

  const [reflection, setReflection] = useState("");
  const [prayer, setPrayer] = useState("");

  const [language, setLanguage] = useState("English");
  const [published, setPublished] = useState(false);

  const [saving, setSaving] = useState(false);

  async function saveReading() {
    if (
      !title.trim() ||
      !readingDate.trim() ||
      !firstReference.trim() ||
      !firstReading.trim() ||
      !gospelReference.trim() ||
      !gospel.trim()
    ) {
      Alert.alert(
        "Missing Information",
        "Title, date, first reading and Gospel are required."
      );
      return;
    }

    try {
      setSaving(true);

      const token =
        await AsyncStorage.getItem("access_token");

      if (!token) {
        Alert.alert(
          "Authentication Required",
          "Please log in as an administrator."
        );
        return;
      }

      const response = await api.post(
        "/api/readings/",
        {
          reading_date: readingDate,
          language,
          liturgical_year: liturgicalYear,
          liturgical_season: season,
          liturgical_color:
            season === "Lent" ||
            season === "Advent"
              ? "Purple"
              : season === "Easter" ||
                season === "Christmas"
              ? "White"
              : season === "Pentecost" ||
                season === "Holy Week"
              ? "Red"
              : "Green",

          feast: feast.trim() || null,
          saint_of_day: saint.trim() || null,

          first_reading_reference:
            firstReference.trim(),
          first_reading: firstReading.trim(),

          responsorial_psalm_reference:
            psalmReference.trim() || null,
          responsorial_psalm:
            psalm.trim() || null,
          responsorial_response:
            psalmResponse.trim() || null,

          second_reading_reference:
            secondReference.trim() || null,
          second_reading:
            secondReading.trim() || null,

          gospel_acclamation:
            gospelAcclamation.trim() || null,

          gospel_reference:
            gospelReference.trim(),
          gospel: gospel.trim(),

          reflection:
            reflection.trim() || null,
          prayer: prayer.trim() || null,

          published,
          approved: published,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          timeout: 20000,
        }
      );

      await saveLocalCopy(response.data);

      Alert.alert(
        "Success",
        published
          ? "Reading published successfully."
          : "Reading saved as a draft."
      );

      clearForm();
    } catch (error: any) {
      console.log(
        "Save reading error:",
        error?.response?.data || error
      );

      // Local fallback keeps admin work available if
      // the backend is temporarily unreachable.
      try {
        await saveLocalFallback();
        Alert.alert(
          "Saved Locally",
          "The backend could not be reached, so the reading was saved on this device."
        );
        clearForm();
      } catch {
        const message =
          error?.response?.data?.detail ||
          "Unable to save the reading.";

        Alert.alert(
          "Save Failed",
          String(message)
        );
      }
    } finally {
      setSaving(false);
    }
  }

  async function saveLocalCopy(data: any) {
    const existing = JSON.parse(
      (await AsyncStorage.getItem("readings")) ||
        "[]"
    );

    const normalized =
      data && typeof data === "object"
        ? data
        : buildLocalReading();

    existing.unshift({
      ...normalized,
      local_id:
        normalized.id ??
        `local-${Date.now()}`,
    });

    await AsyncStorage.setItem(
      "readings",
      JSON.stringify(existing)
    );
  }

  async function saveLocalFallback() {
    const existing = JSON.parse(
      (await AsyncStorage.getItem("readings")) ||
        "[]"
    );

    existing.unshift({
      ...buildLocalReading(),
      local_id: `local-${Date.now()}`,
    });

    await AsyncStorage.setItem(
      "readings",
      JSON.stringify(existing)
    );
  }

  function buildLocalReading() {
    return {
      id: Date.now(),
      title: title.trim(),
      reading_date: readingDate.trim(),
      language,
      liturgical_year: liturgicalYear,
      liturgical_season: season,
      feast: feast.trim(),
      saint_of_day: saint.trim(),
      first_reading_reference:
        firstReference.trim(),
      first_reading: firstReading.trim(),
      responsorial_psalm_reference:
        psalmReference.trim(),
      responsorial_psalm: psalm.trim(),
      responsorial_response:
        psalmResponse.trim(),
      second_reading_reference:
        secondReference.trim(),
      second_reading: secondReading.trim(),
      gospel_acclamation:
        gospelAcclamation.trim(),
      gospel_reference:
        gospelReference.trim(),
      gospel: gospel.trim(),
      reflection: reflection.trim(),
      prayer: prayer.trim(),
      published,
      approved: published,
    };
  }

  function clearForm() {
    setTitle("");
    setReadingDate("");
    setLiturgicalYear("A");
    setSeason("Ordinary Time");
    setFeast("");
    setSaint("");
    setFirstReference("");
    setFirstReading("");
    setPsalmReference("");
    setPsalm("");
    setPsalmResponse("");
    setSecondReference("");
    setSecondReading("");
    setGospelAcclamation("");
    setGospelReference("");
    setGospel("");
    setReflection("");
    setPrayer("");
    setLanguage("English");
    setPublished(false);
  }

  function togglePublished() {
    setPublished((value) => !value);
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={
        Platform.OS === "ios" ? "padding" : undefined
      }
    >
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* HEADER */}
        <View style={styles.header}>
          <View style={styles.headerIcon}>
            <MaterialCommunityIcons
              name="book-plus"
              size={29}
              color="#0B6623"
            />
          </View>

          <View style={styles.headerText}>
            <Text style={styles.title}>
              Add Reading
            </Text>

            <Text style={styles.subtitle}>
              Create a complete Catholic daily reading
            </Text>
          </View>
        </View>

        {/* BASIC INFORMATION */}
        <SectionTitle
          icon="information-circle-outline"
          title="Basic Information"
        />

        <Label text="Title" />

        <TextInput
          style={styles.input}
          placeholder="e.g. Thursday of the 19th Week in Ordinary Time"
          placeholderTextColor="#999"
          value={title}
          onChangeText={setTitle}
        />

        <Label text="Date" />

        <TextInput
          style={styles.input}
          placeholder="YYYY-MM-DD"
          placeholderTextColor="#999"
          value={readingDate}
          onChangeText={setReadingDate}
          keyboardType="numbers-and-punctuation"
        />

        <Label text="Language" />

        <View style={styles.chips}>
          {["English", "Swahili", "Latin"].map(
            (item) => (
              <Pressable
                key={item}
                style={[
                  styles.chip,
                  language === item &&
                    styles.chipActive,
                ]}
                onPress={() =>
                  setLanguage(item)
                }
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

        <Label text="Liturgical Year" />

        <View style={styles.chips}>
          {["A", "B", "C"].map((item) => (
            <Pressable
              key={item}
              style={[
                styles.smallChip,
                liturgicalYear === item &&
                  styles.chipActive,
              ]}
              onPress={() =>
                setLiturgicalYear(item)
              }
            >
              <Text
                style={[
                  styles.chipText,
                  liturgicalYear === item &&
                    styles.chipTextActive,
                ]}
              >
                Year {item}
              </Text>
            </Pressable>
          ))}
        </View>

        <Label text="Liturgical Season" />

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.horizontalList}
        >
          {seasons.map((item) => (
            <Pressable
              key={item}
              style={[
                styles.seasonChip,
                season === item &&
                  styles.chipActive,
              ]}
              onPress={() =>
                setSeason(item)
              }
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

        <Label text="Feast / Celebration" />

        <TextInput
          style={styles.input}
          placeholder="Optional feast or solemnity"
          placeholderTextColor="#999"
          value={feast}
          onChangeText={setFeast}
        />

        <Label text="Saint of the Day" />

        <TextInput
          style={styles.input}
          placeholder="Optional saint"
          placeholderTextColor="#999"
          value={saint}
          onChangeText={setSaint}
        />

        {/* FIRST READING */}
        <SectionTitle
          icon="book-outline"
          title="First Reading"
        />

        <Label text="Bible Reference" />

        <TextInput
          style={styles.input}
          placeholder="e.g. 1 Kings 18:1-2, 41-46"
          placeholderTextColor="#999"
          value={firstReference}
          onChangeText={setFirstReference}
        />

        <TextInput
          style={styles.textArea}
          placeholder="Enter the First Reading..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={firstReading}
          onChangeText={setFirstReading}
        />

        {/* PSALM */}
        <SectionTitle
          icon="musical-notes-outline"
          title="Responsorial Psalm"
        />

        <Label text="Psalm Reference" />

        <TextInput
          style={styles.input}
          placeholder="e.g. Psalm 51:3-4, 5-6, 12-13"
          placeholderTextColor="#999"
          value={psalmReference}
          onChangeText={setPsalmReference}
        />

        <Label text="Response" />

        <TextInput
          style={styles.input}
          placeholder="Enter the psalm response..."
          placeholderTextColor="#999"
          value={psalmResponse}
          onChangeText={setPsalmResponse}
        />

        <TextInput
          style={styles.textArea}
          placeholder="Enter the Responsorial Psalm..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={psalm}
          onChangeText={setPsalm}
        />

        {/* SECOND READING */}
        <SectionTitle
          icon="book-outline"
          title="Second Reading"
        />

        <Label text="Bible Reference" />

        <TextInput
          style={styles.input}
          placeholder="Optional second reading reference"
          placeholderTextColor="#999"
          value={secondReference}
          onChangeText={setSecondReference}
        />

        <TextInput
          style={styles.textArea}
          placeholder="Enter the Second Reading..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={secondReading}
          onChangeText={setSecondReading}
        />

        {/* GOSPEL ACCLAMATION */}
        <SectionTitle
          icon="megaphone-outline"
          title="Gospel Acclamation"
        />

        <TextInput
          style={styles.textAreaSmall}
          placeholder="Enter Gospel Acclamation..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={gospelAcclamation}
          onChangeText={setGospelAcclamation}
        />

        {/* GOSPEL */}
        <SectionTitle
          icon="book-open-outline"
          title="Gospel"
        />

        <Label text="Bible Reference" />

        <TextInput
          style={styles.input}
          placeholder="e.g. Matthew 14:22-33"
          placeholderTextColor="#999"
          value={gospelReference}
          onChangeText={setGospelReference}
        />

        <TextInput
          style={styles.textAreaLarge}
          placeholder="Enter the Gospel..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={gospel}
          onChangeText={setGospel}
        />

        {/* REFLECTION */}
        <SectionTitle
          icon="heart-outline"
          title="Reflection"
        />

        <TextInput
          style={styles.textArea}
          placeholder="Optional reflection or meditation..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={reflection}
          onChangeText={setReflection}
        />

        {/* PRAYER */}
        <SectionTitle
          icon="hand-left-outline"
          title="Prayer"
        />

        <TextInput
          style={styles.textArea}
          placeholder="Optional prayer..."
          placeholderTextColor="#999"
          multiline
          textAlignVertical="top"
          value={prayer}
          onChangeText={setPrayer}
        />

        {/* PUBLISH */}
        <Pressable
          style={styles.publishRow}
          onPress={togglePublished}
        >
          <View
            style={[
              styles.checkbox,
              published && styles.checkboxActive,
            ]}
          >
            {published && (
              <Ionicons
                name="checkmark"
                size={17}
                color="#fff"
              />
            )}
          </View>

          <View style={styles.publishText}>
            <Text style={styles.publishTitle}>
              Publish immediately
            </Text>

            <Text style={styles.publishDescription}>
              Published readings become visible to
              app users after approval.
            </Text>
          </View>
        </Pressable>

        {/* SAVE */}
        <Pressable
          style={[
            styles.saveButton,
            saving && styles.disabled,
          ]}
          onPress={saveReading}
          disabled={saving}
        >
          {saving ? (
            <View style={styles.saveContent}>
              <ActivityIndicator color="#fff" />

              <Text style={styles.saveText}>
                Saving...
              </Text>
            </View>
          ) : (
            <View style={styles.saveContent}>
              <Ionicons
                name="cloud-upload-outline"
                size={21}
                color="#fff"
              />

              <Text style={styles.saveText}>
                Save Reading
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

function Label({
  text,
}: {
  text: string;
}) {
  return (
    <Text style={styles.label}>
      {text}
    </Text>
  );
}

function SectionTitle({
  icon,
  title,
}: {
  icon: any;
  title: string;
}) {
  return (
    <View style={styles.sectionTitle}>
      <Ionicons
        name={icon}
        size={21}
        color="#0B6623"
      />

      <Text style={styles.sectionTitleText}>
        {title}
      </Text>
    </View>
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
    justifyContent: "center",
    alignItems: "center",
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

  sectionTitle: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 18,
    marginBottom: 12,
  },

  sectionTitleText: {
    fontSize: 19,
    fontWeight: "800",
    color: "#222",
    marginLeft: 8,
  },

  label: {
    fontSize: 14,
    color: "#333",
    fontWeight: "700",
    marginBottom: 7,
    marginTop: 4,
  },

  input: {
    minHeight: 52,
    borderWidth: 1,
    borderColor: "#D9DED9",
    borderRadius: 12,
    backgroundColor: "#fff",
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: "#222",
    marginBottom: 12,
  },

  textArea: {
    minHeight: 145,
    borderWidth: 1,
    borderColor: "#D9DED9",
    borderRadius: 12,
    backgroundColor: "#fff",
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: "#222",
    marginBottom: 12,
  },

  textAreaSmall: {
    minHeight: 100,
    borderWidth: 1,
    borderColor: "#D9DED9",
    borderRadius: 12,
    backgroundColor: "#fff",
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: "#222",
    marginBottom: 12,
  },

  textAreaLarge: {
    minHeight: 220,
    borderWidth: 1,
    borderColor: "#D9DED9",
    borderRadius: 12,
    backgroundColor: "#fff",
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: "#222",
    marginBottom: 12,
  },

  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 5,
  },

  chip: {
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#0B6623",
    backgroundColor: "#fff",
    marginRight: 8,
    marginBottom: 8,
  },

  smallChip: {
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#0B6623",
    backgroundColor: "#fff",
    marginRight: 8,
    marginBottom: 8,
  },

  seasonChip: {
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#0B6623",
    backgroundColor: "#fff",
    marginRight: 8,
  },

  chipActive: {
    backgroundColor: "#0B6623",
  },

  chipText: {
    color: "#0B6623",
    fontWeight: "700",
    fontSize: 13,
  },

  chipTextActive: {
    color: "#fff",
  },

  horizontalList: {
    marginBottom: 12,
  },

  publishRow: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#E1E6E2",
    borderRadius: 13,
    padding: 14,
    flexDirection: "row",
    alignItems: "center",
    marginTop: 10,
  },

  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 7,
    borderWidth: 2,
    borderColor: "#0B6623",
    justifyContent: "center",
    alignItems: "center",
  },

  checkboxActive: {
    backgroundColor: "#0B6623",
  },

  publishText: {
    flex: 1,
    marginLeft: 12,
  },

  publishTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: "#222",
  },

  publishDescription: {
    color: "#777",
    fontSize: 12,
    lineHeight: 17,
    marginTop: 3,
  },

  saveButton: {
    minHeight: 55,
    backgroundColor: "#0B6623",
    borderRadius: 13,
    justifyContent: "center",
    alignItems: "center",
    marginTop: 20,
  },

  disabled: {
    opacity: 0.7,
  },

  saveContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
  },

  saveText: {
    color: "#fff",
    fontSize: 17,
    fontWeight: "800",
  },

  footer: {
    textAlign: "center",
    color: "#aaa",
    fontSize: 11,
    marginTop: 20,
  },
});