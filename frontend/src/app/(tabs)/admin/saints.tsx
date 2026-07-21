import { ScrollView, Text } from "react-native";

export default function SaintsScreen() {
  return (
    <ScrollView style={{padding:20}}>
      <Text style={{fontSize:28,fontWeight:"bold"}}>
        Saints Management
      </Text>

      <Text>Saint Peter</Text>
      <Text>Saint Paul</Text>
      <Text>Saint Augustine</Text>
    </ScrollView>
  );
}