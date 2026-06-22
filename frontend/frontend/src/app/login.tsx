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

export default function LoginScreen() {

const [email, setEmail] = useState("");
const [password, setPassword] = useState("");

const login = () => {

if (!email || !password) {

Alert.alert(
"Missing Fields",
"Enter email and password"
);

return;
}

router.replace("/(tabs)");

};

return (

<View style={styles.container}>

<Text style={styles.title}>
Catholic App Login
</Text>

<TextInput
placeholder="Email"
value={email}
onChangeText={setEmail}
style={styles.input}
/>

<TextInput
placeholder="Password"
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
marginBottom:25,
textAlign:"center"
},

input:{
borderWidth:1,
borderColor:"#ccc",
padding:12,
marginBottom:15,
borderRadius:10
},

button:{
backgroundColor:"green",
padding:15,
borderRadius:10
},

buttonText:{
color:"white",
textAlign:"center",
fontWeight:"bold"
}

});