import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { api } from "@/lib/api";

interface SubscriptionStatus {
  active: boolean;
  expires_at?: string | null;
  amount: number;
  currency: string;
}

export default function PaymentScreen() {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    loadStatus();
  }, []);

  async function loadStatus() {
    try {
      const response = await api.get<SubscriptionStatus>("/api/payments/status");
      setStatus(response.data);
    } catch {
      Alert.alert("Unable to check subscription", "Please try again later.");
    } finally {
      setLoading(false);
    }
  }

  async function startPayment() {
    if (!phoneNumber.trim()) {
      Alert.alert("Phone number required", "Enter the M-Pesa number to charge.");
      return;
    }

    try {
      setPaying(true);
      await api.post("/api/payments/subscribe", {
        phone_number: phoneNumber.trim(),
      });
      Alert.alert(
        "Payment request sent",
        "Check the phone you entered and complete the M-Pesa PIN prompt."
      );
      setTimeout(() => {
        void loadStatus();
      }, 8000);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      Alert.alert("Payment failed", detail || "Unable to start the M-Pesa payment.");
    } finally {
      setPaying(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.iconCircle}>
        <MaterialCommunityIcons name="cellphone-check" size={40} color="#0B6623" />
      </View>
      <Text style={styles.title}>Monthly Subscription</Text>
      <Text style={styles.price}>KES 10 / month</Text>
      <Text style={styles.description}>
        Pay via M-Pesa to 0748153302. Enter the phone number that should receive the payment prompt.
      </Text>

      {loading ? (
        <ActivityIndicator color="#0B6623" />
      ) : (
        <Text style={styles.status}>
          {status?.active
            ? `Active until ${new Date(status.expires_at || "").toLocaleDateString()}`
            : "No active subscription"}
        </Text>
      )}

      <TextInput
        style={styles.input}
        placeholder="M-Pesa phone number"
        keyboardType="phone-pad"
        value={phoneNumber}
        onChangeText={setPhoneNumber}
        editable={!paying}
      />

      <Pressable style={styles.button} onPress={startPayment} disabled={paying}>
        {paying ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Pay KES 10</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#F7F9F7",
  },
  iconCircle: {
    alignSelf: "center",
    width: 82,
    height: 82,
    borderRadius: 41,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#EAF4ED",
    marginBottom: 20,
  },
  title: {
    textAlign: "center",
    fontSize: 28,
    fontWeight: "800",
    color: "#0B6623",
  },
  price: {
    textAlign: "center",
    fontSize: 22,
    fontWeight: "700",
    color: "#222",
    marginTop: 8,
  },
  description: {
    textAlign: "center",
    color: "#666",
    lineHeight: 22,
    marginVertical: 18,
  },
  status: {
    textAlign: "center",
    color: "#0B6623",
    fontWeight: "700",
    marginBottom: 18,
  },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D6DED8",
    borderRadius: 10,
    paddingHorizontal: 15,
    paddingVertical: 14,
    fontSize: 16,
    marginBottom: 14,
  },
  button: {
    backgroundColor: "#0B6623",
    borderRadius: 10,
    paddingVertical: 15,
    alignItems: "center",
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "800",
  },
});
