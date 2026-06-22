import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from "react-native";
import { getList, saveList, StorageKeys } from "@/lib/storage";

export default function UploadScreen() {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  const upload = async () => {
    if (!title || !content) {
      Alert.alert("Fill all fields");
      return;
    }

    const pending = await getList(StorageKeys.PENDING_READINGS);

    pending.push({
      id: Date.now().toString(),
      title,
      content,
      status: "pending",
      createdAt: new Date().toISOString(),
    });

    await saveList(StorageKeys.PENDING_READINGS, pending);

    Alert.alert("Uploaded for approval");

    setTitle("");
    setContent("");
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Upload Reading</Text>

      <TextInput
        placeholder="Title"
        value={title}
        onChangeText={setTitle}
        style={styles.input}
      />

      <TextInput
        placeholder="Content"
        value={content}
        onChangeText={setContent}
        multiline
        style={styles.textArea}
      />

      <TouchableOpacity style={styles.btn} onPress={upload}>
        <Text style={styles.btnText}>Submit for Approval</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { fontSize: 26, fontWeight: "bold", marginBottom: 20 },
  input: { borderWidth: 1, padding: 10, marginBottom: 10, borderRadius: 8 },
  textArea: { borderWidth: 1, height: 150, padding: 10, borderRadius: 8 },
  btn: { backgroundColor: "green", padding: 15, marginTop: 15, borderRadius: 10 },
  btnText: { color: "white", textAlign: "center" },
});