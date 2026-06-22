import { View, Text, Pressable, StyleSheet } from "react-native";
import { router } from "expo-router";

export default function Home() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        Catholic Readings & Choir Resource App
      </Text>

      <Pressable
        style={styles.button}
        onPress={() => router.push("/readings")}
      >
        <Text style={styles.buttonText}>Daily Readings</Text>
      </Pressable>

      <Pressable
        style={styles.button}
        onPress={() => router.push("/choir")}
      >
        <Text style={styles.buttonText}>Choir Resources</Text>
      </Pressable>

      <Pressable
        style={styles.button}
        onPress={() => router.push("/downloads")}
      >
        <Text style={styles.buttonText}>Offline Downloads</Text>
      </Pressable>

      <Pressable
        style={styles.button}
        onPress={() => router.push("/admin")}
      >
        <Text style={styles.buttonText}>Admin Panel</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    padding: 25,
    gap: 15,
  },
  title: {
    fontSize: 28,
    fontWeight: "bold",
    marginBottom: 20,
    textAlign: "center",
  },
  button: {
    backgroundColor: "#1e88e5",
    padding: 15,
    borderRadius: 10,
  },
  buttonText: {
    color: "white",
    textAlign: "center",
    fontSize: 18,
  },
});