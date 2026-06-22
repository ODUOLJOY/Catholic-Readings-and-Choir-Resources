import { ScrollView, Text, StyleSheet } from "react-native";

export default function Choir() {
  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Choir Songs</Text>

      <Text>🎵 Holy God We Praise Thy Name</Text>
      <Text>🎵 Ave Maria</Text>
      <Text>🎵 Panis Angelicus</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { fontSize: 28, fontWeight: "bold", marginBottom: 20 },
});