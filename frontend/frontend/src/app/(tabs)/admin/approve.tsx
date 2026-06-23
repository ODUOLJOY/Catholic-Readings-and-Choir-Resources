import { useEffect, useState } from "react";
import { View, Text, Button, FlatList } from "react-native";
import axios from "axios";

export default function ApproveScreen() {
  const [pending, setPending] = useState([]);

  const load = async () => {
    try {
      const res = await axios.get("https://catholic-readings-and-choir-resource-app.onrender.com/admin/pending");
      setPending(res.data || []);
    } catch (err) {
      setPending([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const approve = async (id: number) => {
    await axios.post(`https://catholic-readings-and-choir-resource-app.onrender.com/admin/approve/${id}`);
    load();
  };

  return (
    <View style={{ padding: 20 }}>
      <Text>Pending Readings</Text>

      <FlatList
        data={pending}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <View style={{ marginVertical: 10 }}>
            <Text>{item.title}</Text>
            <Button title="Approve" onPress={() => approve(item.id)} />
          </View>
        )}
      />
    </View>
  );
}