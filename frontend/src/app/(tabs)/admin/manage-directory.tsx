import { useState, useEffect } from "react";
import { ScrollView, StyleSheet, Text, View, TextInput, Button, Alert } from "react-native";
import { api } from "../../../lib/api";

export default function ManageDirectory() {
  const [dioceses, setDioceses] = useState([]);
  const [newDeanery, setNewDeanery] = useState({ name: "", code: "", diocese_id: "" });
  const [newParish, setNewParish] = useState({ name: "", code: "", deanery_id: "", diocese_id: "" });

  useEffect(() => {
    api.get("/api/v1/locations/dioceses?country=KE").then((res) => setDioceses(res.data));
  }, []);

  const handleAddDeanery = async () => {
    try {
      await api.post("/api/v1/locations/deaneries", null, { params: newDeanery });
      Alert.alert("Success", "Deanery added.");
    } catch (e) { Alert.alert("Error", "Failed to add deanery."); }
  };

  const handleAddParish = async () => {
    try {
      await api.post("/api/v1/locations/parishes", null, { params: newParish });
      Alert.alert("Success", "Parish added.");
    } catch (e) { Alert.alert("Error", "Failed to add parish."); }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Manage Directory</Text>
      
      <View style={styles.section}>
        <Text style={styles.subtitle}>Add Deanery</Text>
        <TextInput placeholder="Name" style={styles.input} onChangeText={(v) => setNewDeanery({...newDeanery, name: v})} />
        <TextInput placeholder="Code" style={styles.input} onChangeText={(v) => setNewDeanery({...newDeanery, code: v})} />
        <TextInput placeholder="Diocese ID" style={styles.input} onChangeText={(v) => setNewDeanery({...newDeanery, diocese_id: v})} />
        <Button title="Add Deanery" onPress={handleAddDeanery} />
      </View>

      <View style={styles.section}>
        <Text style={styles.subtitle}>Add Parish</Text>
        <TextInput placeholder="Name" style={styles.input} onChangeText={(v) => setNewParish({...newParish, name: v})} />
        <TextInput placeholder="Code" style={styles.input} onChangeText={(v) => setNewParish({...newParish, code: v})} />
        <TextInput placeholder="Deanery ID" style={styles.input} onChangeText={(v) => setNewParish({...newParish, deanery_id: v})} />
        <TextInput placeholder="Diocese ID" style={styles.input} onChangeText={(v) => setNewParish({...newParish, diocese_id: v})} />
        <Button title="Add Parish" onPress={handleAddParish} />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20 },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 20 },
  subtitle: { fontSize: 18, fontWeight: "600", marginBottom: 10 },
  input: { borderWidth: 1, borderColor: "#ccc", padding: 10, marginBottom: 10, borderRadius: 5 },
  section: { marginBottom: 30, padding: 15, backgroundColor: "#fff", borderRadius: 8 }
});
