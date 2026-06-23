import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  Button,
  Image,
  ScrollView,
} from "react-native";

import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";

import axios from "axios";

export default function Admin() {
  const [title, setTitle] = useState("");

  const [file, setFile] = useState<any>(null);

  async function pickImage() {
    const result =
      await ImagePicker.launchImageLibraryAsync({
        mediaTypes:
          ImagePicker.MediaTypeOptions.All,
      });

    if (!result.canceled) {
      setFile(result.assets[0]);
    }
  }

  async function pickFile() {
    const result =
      await DocumentPicker.getDocumentAsync({
        type: "*/*",
      });

    if (!result.canceled) {
      setFile(result.assets[0]);
    }
  }

  async function upload() {
    if (!file) return;

    const data = new FormData();

    data.append("title", title);

    data.append("file", {
      uri: file.uri,
      name: file.name || "upload",
      type:
        file.mimeType ||
        "application/octet-stream",
    } as any);

    await axios.post(
  "https://catholic-readings-and-choir-resource-app.onrender.com/upload",
      data,
      {
        headers: {
          "Content-Type":
            "multipart/form-data",
        },
      }
    );

    alert("Uploaded");
  }

  return (
    <ScrollView style={{ padding: 20 }}>
      <Text>Admin Upload</Text>

      <TextInput
        placeholder="Title"
        value={title}
        onChangeText={setTitle}
        style={{
          borderWidth: 1,
          padding: 10,
          marginVertical: 10,
        }}
      />

      <Button
        title="Choose Image"
        onPress={pickImage}
      />

      <Button
        title="Choose Video / Audio / PDF"
        onPress={pickFile}
      />

      {file?.uri && (
        <Image
          source={{ uri: file.uri }}
          style={{
            width: 200,
            height: 200,
            marginTop: 20,
          }}
        />
      )}

      <Button
        title="Upload"
        onPress={upload}
      />
    </ScrollView>
  );
}