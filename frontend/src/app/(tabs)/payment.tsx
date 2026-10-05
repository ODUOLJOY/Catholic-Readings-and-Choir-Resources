import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { router } from "expo-router";
import { api } from "@/lib/api";
import { classifyRequestFailure, RequestFailure } from "@/lib/requestFailure";
import { ErrorState, LoadingState } from "@/components/ScreenStates";

interface SubscriptionPlan {
  id: string;
  name: string;
  amount: number;
  currency: string;
  period_days: number;
  features: string[];
  payment_method: string;
  paybill: string | null;
}

interface SubscriptionStatus {
  active: boolean;
  plan: string;
  expires_at: string | null;
  amount: number;
  currency: string;
  features: string[];
}

interface PaymentRecord {
  id: number;
  amount: number;
  currency: string;
  status: string;
  mpesa_receipt_number: string | null;
  result_description: string | null;
  created_at: string;
}

/** How long after a prompt to keep re-checking status, and how often. */
const POLL_INTERVALS_MS = [4_000, 8_000, 15_000];

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toLocaleDateString();
}

export default function PaymentScreen() {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [plan, setPlan] = useState<SubscriptionPlan | null>(null);
  const [status, setStatus] = useState<SubscriptionStatus | null>(null);
  const [history, setHistory] = useState<PaymentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [awaitingCallback, setAwaitingCallback] = useState(false);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [signedIn, setSignedIn] = useState(true);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const loadStatus = useCallback(async (): Promise<boolean> => {
    const [statusRes, historyRes] = await Promise.allSettled([
      api.get<SubscriptionStatus>("/api/payments/status"),
      api.get<{ payments: PaymentRecord[] }>("/api/payments/history"),
    ]);

    let confirmed = false;
    if (statusRes.status === "fulfilled") {
      setStatus(statusRes.value.data);
      setSignedIn(true);
      setFailure(null);
      confirmed = statusRes.value.data.active;
    } else {
      const failure = classifyRequestFailure(statusRes.reason, {
        fallbackNotFound: "Subscription status unavailable.",
      });
      // A signed-out visitor is expected here, not an error worth an alert.
      if (failure.kind === "unauthorized") {
        setSignedIn(false);
      } else {
        setFailure(failure);
      }
    }

    if (historyRes.status === "fulfilled") {
      setHistory(historyRes.value.data.payments ?? []);
    }

    return confirmed;
  }, []);

  useEffect(() => {
    let active = true;

    async function load() {
      // Plans are public, so they load even when the visitor is signed out. The
      // price, plan name and paybill used to be literal strings in this file,
      // which meant any configuration change showed a stale price on screen.
      const [planOutcome] = await Promise.allSettled([
        api.get<{ plans: SubscriptionPlan[] }>("/api/payments/plans"),
      ]);
      if (!active) {
        return;
      }
      if (planOutcome.status === "fulfilled") {
        setPlan(planOutcome.value.data.plans?.[0] ?? null);
      }

      await loadStatus();
      if (active) {
        setLoading(false);
      }
    }

    void Promise.resolve().then(load);

    return () => {
      active = false;
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };
  }, [loadStatus]);

  /**
   * Re-check status a few times after the prompt.
   *
   * The callback is asynchronous and server-driven, so activation can land after
   * the member returns to the app. Polling replaces the single fixed 8-second
   * reload, which either checked too early (showing "not subscribed" while the
   * PIN was still being entered) or too late for a fast connection.
   */
  function schedulePolling() {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setAwaitingCallback(true);

    POLL_INTERVALS_MS.forEach((delay, index) => {
      const isLastAttempt = index === POLL_INTERVALS_MS.length - 1;
      const timer = setTimeout(() => {
        void loadStatus().then((confirmed) => {
          if (confirmed) {
            // Settled early: stop the remaining attempts instead of continuing
            // to poll, and clear the waiting message.
            timers.current.forEach(clearTimeout);
            timers.current = [];
            setAwaitingCallback(false);
            return;
          }
          if (isLastAttempt) {
            setAwaitingCallback(false);
            Alert.alert(
              "Payment not confirmed",
              "If you completed the M-Pesa payment, it may take a moment to appear. Pull to refresh or check again shortly."
            );
          }
        });
      }, delay);
      timers.current.push(timer);
    });
  }

  async function startPayment() {
    if (!signedIn) {
      Alert.alert("Sign in required", "Sign in to subscribe with M-Pesa.");
      return;
    }
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
      schedulePolling();
    } catch (error: unknown) {
      // The backend distinguishes a rejected number (422), an unavailable
      // provider (502) and the rate limit (429); showing its `detail` beats the
      // single generic message this screen used for all of them.
      const failure = classifyRequestFailure(error, {
        fallbackNotFound: "Unable to start the payment.",
      });
      Alert.alert("Payment failed", failure.message);
    } finally {
      setPaying(false);
    }
  }

  if (loading) {
    return <LoadingState label="Loading subscription…" />;
  }

  const features = status?.active && status.features?.length
    ? status.features
    : plan?.features ?? [];

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.iconCircle}>
        <MaterialCommunityIcons name="cellphone-check" size={40} color="#0B6623" />
      </View>
      <Text style={styles.title}>{plan?.name ?? "Monthly Subscription"}</Text>
      <Text style={styles.price}>
        {plan ? `${plan.currency} ${plan.amount} / ${plan.period_days === 30 ? "month" : `${plan.period_days} days`}` : ""}
      </Text>
      <Text style={styles.description}>
        {plan?.payment_method === "M-Pesa" && plan.paybill
          ? `Pay via M-Pesa to ${plan.paybill}. Enter the phone number that should receive the payment prompt.`
          : "Enter the phone number that should receive the payment prompt."}
      </Text>

      {failure ? <ErrorState message={failure.message} onRetry={() => void loadStatus()} /> : null}

      {!signedIn ? (
        <ErrorState
          message="Sign in to check your subscription and pay."
          onRetry={() => router.push("/(auth)/login")}
          retryLabel="Sign in"
        />
      ) : (
        <Text style={styles.status}>
          {status?.active
            ? `Active until ${formatDate(status.expires_at)}`
            : awaitingCallback
              ? "Waiting for M-Pesa confirmation…"
              : "No active subscription"}
        </Text>
      )}

      {features.length > 0 ? (
        <View style={styles.features}>
          <Text style={styles.featuresTitle}>
            {status?.active ? "Included with your subscription" : "Subscription includes"}
          </Text>
          {features.map((feature) => (
            <View key={feature} style={styles.featureRow}>
              <MaterialCommunityIcons name="check-circle" size={16} color="#0B6623" />
              <Text style={styles.featureText}>{feature}</Text>
            </View>
          ))}
        </View>
      ) : null}

      <TextInput
        style={styles.input}
        placeholder="M-Pesa phone number"
        keyboardType="phone-pad"
        value={phoneNumber}
        onChangeText={setPhoneNumber}
        editable={!paying}
        accessibilityLabel="M-Pesa phone number"
      />

      <Pressable
        style={[styles.button, paying && styles.buttonDisabled]}
        onPress={() => void startPayment()}
        disabled={paying || !signedIn}
        accessibilityRole="button"
      >
        {paying ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>
            {plan ? `Pay ${plan.currency} ${plan.amount}` : "Pay"}
          </Text>
        )}
      </Pressable>

      {history.length > 0 ? (
        <View style={styles.history}>
          <Text style={styles.historyTitle}>Payment history</Text>
          {history.map((payment) => (
            <View key={payment.id} style={styles.historyRow}>
              <View style={styles.historyMain}>
                <Text style={styles.historyAmount}>
                  {payment.currency} {payment.amount}
                </Text>
                <Text style={styles.historyDate}>
                  {formatDate(payment.created_at)}
                  {payment.mpesa_receipt_number ? ` · ${payment.mpesa_receipt_number}` : ""}
                </Text>
              </View>
              <Text
                style={[
                  styles.historyStatus,
                  payment.status === "completed" && styles.historyStatusActive,
                  payment.status === "failed" && styles.historyStatusFailed,
                ]}
              >
                {payment.status}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
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
  features: {
    backgroundColor: "#fff",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E6EAE7",
    padding: 14,
    marginBottom: 16,
  },
  featuresTitle: {
    fontWeight: "700",
    color: "#222",
    marginBottom: 8,
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 6,
  },
  featureText: {
    marginLeft: 8,
    color: "#444",
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
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "800",
  },
  history: {
    marginTop: 28,
    backgroundColor: "#fff",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E6EAE7",
    padding: 14,
  },
  historyTitle: {
    fontWeight: "700",
    color: "#222",
    marginBottom: 10,
  },
  historyRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: "#F0F2F0",
  },
  historyMain: {
    flex: 1,
  },
  historyAmount: {
    fontWeight: "700",
    color: "#222",
  },
  historyDate: {
    color: "#777",
    fontSize: 12,
    marginTop: 2,
  },
  historyStatus: {
    fontSize: 12,
    fontWeight: "700",
    color: "#777",
    textTransform: "uppercase",
    marginLeft: 10,
  },
  historyStatusActive: {
    color: "#0B6623",
  },
  historyStatusFailed: {
    color: "#8A1C13",
  },
});