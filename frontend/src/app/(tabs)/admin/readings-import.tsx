import { useState } from "react";
import { View, Text, StyleSheet, Button, Alert, TextInput, ScrollView } from "react-native";
import { api } from "../../../lib/api";

export default function ReadingsImport() {
  const [jsonContent, setJsonContent] = useState("");
  const [preview, setPreview] = useState(null);

  const handlePreview = () => {
    try {
      const data = JSON.parse(jsonContent);
      setPreview(data);
    } catch (e) {
      Alert.alert("Error", "Invalid JSON");
    }
  };

  const handleImport = async () => {
    try {
      await api.post("/api/v1/liturgy/admin/import", preview);
      Alert.alert("Success", "Import successful");
      setPreview(null);
      setJsonContent("");
    } catch (e) {
      Alert.alert("Error", "Import failed");
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Import Liturgical Readings</Text>
      <TextInput
        style={styles.input}
        multiline
        placeholder="Paste JSON here"
        value={jsonContent}
        onChangeText={setJsonContent}
      />
      <Button title="Preview" onPress={handlePreview} />
      
      {preview && (
        <View style={styles.preview}>
          <Text style={styles.subtitle}>Preview</Text>
          <Text>{JSON.stringify(preview, null, 2)}</Text>
          <Button title="Confirm Import" onPress={handleImport} />
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20 },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 20 },
  input: { height: 200, borderWidth: 1, borderColor: "#ccc", marginBottom: 20, padding: 10 },
  preview: { marginTop: 20, padding: 10, borderWidth: 1, borderColor: "#ccc" },
  subtitle: { fontSize: 18, fontWeight: "600", marginBottom: 10 },
});
