import { useEffect, useState } from "react";
import { View, Text, FlatList } from "react-native";

export default function Readings() {
  const [readings, setReadings] = useState([]);

  const load = async () => {
    try {
      const response = await fetch(
        "http://127.0.0.1:8000/readings"
      );

      const data = await response.json();

      setReadings(data || []);
    } catch (err) {
      console.log(err);
      setReadings([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <View style={{ padding:20 }}>
      <Text>Daily Readings</Text>

      <FlatList
        data={readings}
        keyExtractor={(item:any) => item.id.toString()}
        renderItem={({ item }:any) => (
          <View style={{ marginBottom:20 }}>
            <Text>{item.title}</Text>
            <Text>{item.content}</Text>
          </View>
        )}
      />
    </View>
  );
}