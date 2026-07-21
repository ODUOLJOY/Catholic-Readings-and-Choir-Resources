import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { router } from "expo-router";

export default function Dashboard() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Admin Dashboard</Text>

      <TouchableOpacity style={styles.btn} onPress={() => router.push("/(tabs)/admin/upload")}>
        <Text style={styles.txt}>Upload Reading</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.btn} onPress={() => router.push("/(tabs)/admin/approve")}>
        <Text style={styles.txt}>Approve Readings</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.btn}>
        <Text style={styles.txt}>Manage Saints</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.btn}>
        <Text style={styles.txt}>Manage Choir</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { fontSize: 28, fontWeight: "bold", marginBottom: 20 },
  btn: { backgroundColor: "green", padding: 15, marginBottom: 10, borderRadius: 10 },
  txt: { color: "white", textAlign: "center" },
});