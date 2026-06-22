import { useState } from "react";

import {
View,
Text,
TextInput,
TouchableOpacity,
StyleSheet,
Alert
} from "react-native";

import { router } from "expo-router";

export default function AdminLogin() {

const [password, setPassword] =
useState("");

const login = () => {

if (password === "Otieno@katua") {

router.replace(
"/(tabs)/admin/dashboard"
);

} else {

Alert.alert(
"Access Denied",
"Wrong password"
);

}

};

return (

<View style={styles.container}>

<Text style={styles.title}>
Admin Login
</Text>

<TextInput
placeholder="Admin Password"
secureTextEntry
value={password}
onChangeText={setPassword}
style={styles.input}
/>

<TouchableOpacity
style={styles.button}
onPress={login}
>

<Text style={styles.buttonText}>
Login
</Text>

</TouchableOpacity>

</View>

);

}

const styles = StyleSheet.create({

container:{
flex:1,
justifyContent:"center",
padding:20
},

title:{
fontSize:30,
fontWeight:"bold",
marginBottom:20,
textAlign:"center"
},

input:{
borderWidth:1,
borderColor:"#ccc",
padding:12,
borderRadius:10,
marginBottom:20
},

button:{
backgroundColor:"green",
padding:15,
borderRadius:10
},

buttonText:{
color:"white",
fontWeight:"bold",
textAlign:"center"
}

});