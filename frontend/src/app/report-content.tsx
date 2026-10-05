import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";

import { defaultReportLabels, ReportForm } from "@/components/ReportModal";
import {
  communityService,
  isReportableResourceType,
} from "@/services/communityService";

/**
 * Route target for the shared `ReportButton`, used by the reading, saint and choir
 * detail screens. It renders the same `ReportForm` the community screens use, so
 * there is one reporting implementation rather than a second one for catalogue
 * content.
 */
export default function ReportContentScreen() {
  const { resourceType, resourceId } = useLocalSearchParams<{
    resourceType?: string;
    resourceId?: string;
  }>();

  const parsedId = Number(resourceId);
  const validType = resourceType && isReportableResourceType(resourceType);
  const validId = Number.isInteger(parsedId) && parsedId > 0;

  if (!validType || !validId) {
    return (
      <View style={styles.center}>
        <Text style={styles.invalidTitle}>This content cannot be reported</Text>
        <Text style={styles.invalidBody}>
          The report link is incomplete, so there is nothing to send to moderation.
        </Text>
        <Text style={styles.backLink} onPress={() => router.back()}>
          Go back
        </Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{defaultReportLabels.title}</Text>
      <Text style={styles.subtitle}>
        {resourceType.replaceAll("_", " ")} #{parsedId}
      </Text>
      <ReportForm
        resourceType={resourceType}
        resourceId={parsedId}
        onSubmit={(payload) => communityService.submitReport(payload)}
        labels={defaultReportLabels}
        onFinished={() => setTimeout(() => router.back(), 1400)}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 20, paddingBottom: 40 },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#F7F9F7",
  },
  title: { fontSize: 24, fontWeight: "800", color: "#0B6623" },
  subtitle: { color: "#59665C", marginTop: 4, marginBottom: 6, textTransform: "capitalize" },
  invalidTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#8A1C13",
    textAlign: "center",
  },
  invalidBody: {
    color: "#59665C",
    textAlign: "center",
    marginTop: 10,
    lineHeight: 20,
  },
  backLink: {
    marginTop: 18,
    color: "#0B6623",
    fontWeight: "700",
  },
});