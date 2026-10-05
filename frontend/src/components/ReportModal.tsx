import React, { useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  defaultReportLabels,
  describeError,
  REPORT_CATEGORIES,
  ReportCategory,
  ReportFormLabels,
  ReportResult,
  ReportableResourceType,
} from "@/services/communityService";

export type { ReportFormLabels };
export { defaultReportLabels };

export type ReportFormPayload = {
  resourceType: ReportableResourceType;
  resourceId: number;
  category: ReportCategory;
  reason: string;
  description: string;
};

type SubmitHandler = (
  payload: ReportFormPayload,
) => Promise<ReportResult>;

/**
 * The one reporting form in the app.
 *
 * The previous implementation posted a free-text reason with the server's default
 * `category` of "other", which meant every report reached a moderator queue
 * without a triage category, and it hid the duplicate-report response and the
 * server's reason behind a generic "failed to submit". This form makes the
 * category explicit, validates before sending, and surfaces what the server
 * actually said.
 */
export function ReportForm({
  resourceType,
  resourceId,
  onSubmit,
  labels,
  onFinished,
}: {
  resourceType: ReportableResourceType;
  resourceId: number;
  onSubmit: SubmitHandler;
  labels: ReportFormLabels;
  onFinished?: (result: ReportResult) => void;
}) {
  const [category, setCategory] = useState<ReportCategory | null>(null);
  const [reason, setReason] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<ReportResult | null>(null);

  async function submit() {
    if (submitting) return;
    setError(null);

    if (!category) {
      setError("Choose the category that best describes the problem.");
      return;
    }
    if (reason.trim().length < 3) {
      setError("Add a short reason so a moderator knows what to look at.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await onSubmit({
        resourceType,
        resourceId,
        category,
        reason: reason.trim(),
        description: description.trim(),
      });
      setSuccess(result);
      onFinished?.(result);
    } catch (submitError) {
      setError(describeError(submitError, "Your report could not be submitted."));
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <View style={styles.successBox}>
        <Text style={styles.successTitle}>
          {success.duplicate ? "Already reported" : "Report received"}
        </Text>
        <Text style={styles.successBody}>
          {success.message ??
            (success.duplicate
              ? "You have already reported this content and a moderator will review it."
              : "A moderator will review this and you will see the outcome on your report.")}
        </Text>
        <Text style={styles.successMeta}>Reference #{success.report_id}</Text>
      </View>
    );
  }

  return (
    <View>
      <Text style={styles.label}>Category</Text>
      <View style={styles.chips}>
        {REPORT_CATEGORIES.map((option) => (
          <Pressable
            key={option.key}
            style={[styles.chip, category === option.key && styles.chipSelected]}
            onPress={() => setCategory(option.key)}
            accessibilityRole="button"
            accessibilityState={{ selected: category === option.key }}
          >
            <Text style={[styles.chipText, category === option.key && styles.chipTextSelected]}>
              {option.label}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>Reason</Text>
      <TextInput
        value={reason}
        onChangeText={setReason}
        style={styles.input}
        placeholder={labels.reasonPlaceholder}
        maxLength={100}
        multiline
      />

      <Text style={styles.label}>Details (optional)</Text>
      <TextInput
        value={description}
        onChangeText={setDescription}
        style={[styles.input, styles.multiline]}
        placeholder={labels.descriptionPlaceholder}
        maxLength={2000}
        multiline
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable style={styles.button} onPress={submit} disabled={submitting}>
        <Text style={styles.buttonText}>
          {submitting ? labels.submittingLabel : labels.submitLabel}
        </Text>
      </Pressable>
      <Text style={styles.footnote}>{labels.intro}</Text>
    </View>
  );
}

export function ReportModal({
  visible,
  onClose,
  resourceType,
  resourceId,
  onSubmit,
  labels,
  title,
}: {
  visible: boolean;
  onClose: () => void;
  resourceType: ReportableResourceType;
  resourceId: number;
  onSubmit: SubmitHandler;
  labels: ReportFormLabels;
  title: string;
}) {
  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.sheetContent}>
            <Text style={styles.title}>{title}</Text>
            <ReportForm
              resourceType={resourceType}
              resourceId={resourceId}
              onSubmit={onSubmit}
              labels={labels}
              onFinished={() => setTimeout(onClose, 1200)}
            />
          </ScrollView>
          <Pressable style={styles.closeButton} onPress={onClose}>
            <Text style={styles.closeText}>Close</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(10, 26, 15, 0.55)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    paddingHorizontal: 18,
    paddingBottom: 26,
    maxHeight: "90%",
  },
  sheetContent: {
    paddingTop: 18,
    paddingBottom: 12,
  },
  title: {
    fontSize: 21,
    fontWeight: "800",
    color: "#0B6623",
    marginBottom: 6,
  },
  label: {
    marginTop: 14,
    marginBottom: 6,
    fontWeight: "600",
    color: "#26382B",
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    borderWidth: 1,
    borderColor: "#B9C9BD",
    borderRadius: 18,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipSelected: {
    backgroundColor: "#0B6623",
    borderColor: "#0B6623",
  },
  chipText: {
    color: "#28412F",
    fontWeight: "600",
  },
  chipTextSelected: {
    color: "#fff",
  },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D5DED7",
    borderRadius: 10,
    padding: 12,
  },
  multiline: {
    minHeight: 88,
    textAlignVertical: "top",
  },
  error: {
    color: "#8A1C13",
    marginTop: 12,
    lineHeight: 20,
  },
  button: {
    backgroundColor: "#0B6623",
    padding: 14,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 14,
  },
  buttonText: {
    color: "#fff",
    fontWeight: "700",
  },
  footnote: {
    color: "#6C7A71",
    marginTop: 12,
    fontSize: 12,
    lineHeight: 18,
  },
  successBox: {
    backgroundColor: "#EDF3EE",
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  successTitle: {
    color: "#0B6623",
    fontWeight: "800",
    fontSize: 17,
  },
  successBody: {
    color: "#2F4234",
    marginTop: 8,
    lineHeight: 20,
  },
  successMeta: {
    color: "#6C7A71",
    marginTop: 10,
    fontSize: 12,
  },
  closeButton: {
    backgroundColor: "#EAF2EC",
    padding: 13,
    borderRadius: 10,
    alignItems: "center",
  },
  closeText: {
    color: "#0B6623",
    fontWeight: "700",
  },
});