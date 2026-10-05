import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { EmptyState, ErrorState, LoadingState } from "@/components/ScreenStates";
import {
  communityService,
  CommunityAuditRecord,
  describeError,
} from "@/services/communityService";

const PAGE_SIZES = [50, 100, 250];

/**
 * Scoped audit log. The server filters by the caller's authorized scopes and caps
 * the page at its own maximum, so the screen only has to expose the limit and an
 * explicit refresh rather than pretending it can page the whole history.
 */
export default function CommunityAuditScreen() {
  const [records, setRecords] = useState<CommunityAuditRecord[]>([]);
  const [limit, setLimit] = useState(PAGE_SIZES[0]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Guards against two failure modes seen in the field: a slow response for a
  // previous limit overwriting the current one, and retry/limit presses piling up
  // concurrent failing requests. Only the newest request may write state.
  const requestIdRef = useRef(0);

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
      const requestId = ++requestIdRef.current;
      const isStale = () => requestId !== requestIdRef.current;

      if (options?.silent) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const result = await communityService.getAuditLog(limit);
        if (isStale()) return;
        setRecords(result);
      } catch (loadError) {
        if (isStale()) return;
        setError(
          describeError(loadError, "The audit log is unavailable for your current scope."),
        );
      } finally {
        if (isStale()) return;
        setLoading(false);
        setRefreshing(false);
      }
    },
    [limit],
  );

  useEffect(() => {
    // Deferred so the loading state is not set synchronously inside the effect
    // body. The request sequence guard, not this deferral, is what makes a limit
    // change safe: a superseded request can no longer write state when it lands.
    const timer = setTimeout(() => {
      void load();
    }, 0);
    return () => clearTimeout(timer);
  }, [load]);

  if (loading) {
    return <LoadingState label="Loading the audit log…" />;
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Administrative audit log</Text>
      <Text style={styles.help}>
        Moderation, membership, role and message actions recorded inside your authorized scopes.
      </Text>

      <View style={styles.toolbar}>
        {PAGE_SIZES.map((size) => (
          <Pressable
            key={size}
            style={[styles.limitButton, limit === size && styles.limitButtonActive]}
            onPress={() => setLimit(size)}
          >
            <Text style={[styles.limitText, limit === size && styles.limitTextActive]}>
              {size}
            </Text>
          </Pressable>
        ))}
        <Pressable style={styles.refresh} onPress={() => void load({ silent: true })}>
          <Text style={styles.refreshText}>{refreshing ? "Refreshing…" : "Refresh"}</Text>
        </Pressable>
      </View>

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      {records.length === 0 ? (
        <EmptyState message="No audit actions are available in your authorized scope." />
      ) : (
        records.map((record) => (
          <View key={record.id} style={styles.card}>
            <Text style={styles.action}>{record.action}</Text>
            <Text style={styles.body}>
              {record.target_type} #{record.target_id ?? "—"} · {record.scope_type ?? "global"}{" "}
              #{record.scope_id ?? "—"}
            </Text>
            <Text style={styles.meta}>
              {record.actor_type} #{record.actor_id ?? "system"} ·{" "}
              {new Date(record.created_at).toLocaleString()}
            </Text>
            {record.reason ? <Text style={styles.body}>{record.reason}</Text> : null}
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 20, paddingBottom: 44 },
  title: { fontSize: 24, fontWeight: "800", color: "#0B6623", marginBottom: 6 },
  help: { color: "#59665C", lineHeight: 20 },
  toolbar: { flexDirection: "row", gap: 8, alignItems: "center", marginVertical: 12 },
  limitButton: {
    borderWidth: 1,
    borderColor: "#B9C9BD",
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  limitButtonActive: { backgroundColor: "#0B6623", borderColor: "#0B6623" },
  limitText: { color: "#28412F", fontWeight: "600", fontSize: 12 },
  limitTextActive: { color: "#fff" },
  refresh: { marginLeft: "auto", paddingVertical: 6 },
  refreshText: { color: "#0B6623", fontWeight: "700", fontSize: 13 },
  card: { backgroundColor: "#fff", padding: 13, borderRadius: 10, marginBottom: 8 },
  action: { color: "#163C23", fontWeight: "700" },
  body: { color: "#444", marginTop: 5, lineHeight: 20 },
  meta: { color: "#7A847D", fontSize: 12, marginTop: 6 },
});