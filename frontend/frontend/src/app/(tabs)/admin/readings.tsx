import { useState } from "react";
import {
View,
Text,
TextInput,
TouchableOpacity,
StyleSheet,
Alert
} from "react-native";

import AsyncStorage from "@react-native-async-storage/async-storage";

export default function AdminReadings() {

const [title,setTitle] = useState("");
const [content,setContent] = useState("");

const saveReading = async () => {

const existing =
JSON.parse(
(await AsyncStorage.getItem("readings"))
|| "[]"
);

existing.push({
title,
content
});

await AsyncStorage.setItem(
"readings",
JSON.stringify(existing)
);

Alert.alert("Saved");

setTitle("");
setContent("");
};

return (

<View style={styles.container}>

<Text style={styles.title}>
Upload Reading
</Text>

<TextInput
placeholder="Title"
value={title}
onChangeText={setTitle}
style={styles.input}
/>

<TextInput
placeholder="Content"
multiline
value={content}
onChangeText={setContent}
style={styles.textArea}
/>

<TouchableOpacity
style={styles.btn}
onPress={saveReading}
>

<Text style={styles.btnText}>
Upload
</Text>

</TouchableOpacity>

</View>

);
}

const styles = StyleSheet.create({

container:{
flex:1,
padding:20
},

title:{
fontSize:26,
fontWeight:"bold",
marginBottom:20
},

input:{
borderWidth:1,
padding:12,
marginBottom:10,
borderRadius:8
},

textArea:{
borderWidth:1,
height:150,
padding:12,
borderRadius:8,
marginBottom:20
},

btn:{
backgroundColor:"green",
padding:15,
borderRadius:10
},

btnText:{
color:"white",
textAlign:"center"
}

});