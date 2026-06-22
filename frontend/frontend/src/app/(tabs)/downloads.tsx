import { View, Text, StyleSheet } from "react-native";

export default function Downloads() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Offline Downloads</Text>

      <Text>No saved readings yet</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container:{
    flex:1,
    justifyContent:"center",
    alignItems:"center",
  },
  title:{
    fontSize:28,
    fontWeight:"bold",
  }
});