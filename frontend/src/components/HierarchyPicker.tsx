import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  DioceseNode,
  EcclesiasticalProvinceNode,
  HierarchyNode,
  ParishNode,
  hierarchyService,
} from "@/services/hierarchyService";

export type HierarchyStep =
  | "country"
  | "province"
  | "diocese"
  | "deanery"
  | "parish";

export interface HierarchySelection {
  country: HierarchyNode | null;
  province: EcclesiasticalProvinceNode | null;
  diocese: DioceseNode | null;
  deanery: HierarchyNode | null;
  parish: ParishNode | null;
}

export const EMPTY_SELECTION: HierarchySelection = {
  country: null,
  province: null,
  diocese: null,
  deanery: null,
  parish: null,
};

const STEPS: HierarchyStep[] = [
  "country",
  "province",
  "diocese",
  "deanery",
  "parish",
];

const STEP_TITLE: Record<HierarchyStep, string> = {
  country: "Country",
  province: "Ecclesiastical Province",
  diocese: "Diocese or Archdiocese",
  deanery: "Deanery",
  parish: "Parish",
};

const STEP_PLURAL: Record<HierarchyStep, string> = {
  country: "Countries",
  province: "Ecclesiastical Provinces",
  diocese: "Dioceses",
  deanery: "Deaneries",
  parish: "Parishes",
};

function errorMessage(error: unknown): string {
  const apiError = error as {
    response?: { data?: { detail?: string } };
    message?: string;
  };
  return (
    apiError?.response?.data?.detail ??
    apiError?.message ??
    "Could not load the Catholic directory."
  );
}

/**
 * Fetch the children of whichever node is the current parent.
 *
 * This is deliberately pure: it never touches React state, so it can be called
 * from an effect without triggering a cascading render.
 */
async function fetchOptions(
  step: HierarchyStep,
  current: HierarchySelection
): Promise<HierarchyNode[]> {
  if (step === "country") {
    return (await hierarchyService.listCountries()).results;
  }
  if (step === "province") {
    if (!current.country) return [];
    return (await hierarchyService.listProvinces(current.country.id)).results;
  }
  if (step === "diocese") {
    if (!current.province) return [];
    return (await hierarchyService.listDioceses(current.province.id)).results;
  }
  if (step === "deanery") {
    if (!current.diocese) return [];
    return (await hierarchyService.listDeaneries(current.diocese.id)).results;
  }
  if (!current.deanery) return [];
  return (await hierarchyService.listParishes(current.deanery.id)).results;
}

interface LoadedState {
  /** Identifies which request the options belong to. */
  key: string;
  options: HierarchyNode[];
  error: string | null;
}

interface HierarchyPickerProps {
  /** Seed the picker with an already-saved location. */
  initialSelection?: HierarchySelection;
  onChange?: (selection: HierarchySelection) => void;
}

export function HierarchyPicker({
  initialSelection,
  onChange,
}: HierarchyPickerProps) {
  const [selection, setSelection] = useState<HierarchySelection>(
    initialSelection ?? EMPTY_SELECTION
  );
  const [step, setStep] = useState<HierarchyStep>(
    initialSelection?.parish ? "parish" : "country"
  );
  const [search, setSearch] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<LoadedState>({
    key: "",
    options: [],
    error: null,
  });

  const requestKey = `${step}:${selection.country?.id ?? ""}:${
    selection.province?.id ?? ""
  }:${selection.diocese?.id ?? ""}:${selection.deanery?.id ?? ""}:${attempt}`;

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const options = await fetchOptions(step, selection);
        if (!active) return;
        setLoaded({ key: requestKey, options: options ?? [], error: null });
      } catch (error) {
        if (!active) return;
        setLoaded({ key: requestKey, options: [], error: errorMessage(error) });
      }
    })();

    // Ignore a response that arrives after the user has moved on, so a slow
    // request can never overwrite the branch that is actually on screen.
    return () => {
      active = false;
    };
  }, [step, selection, requestKey]);

  const loading = loaded.key !== requestKey;
  const error = loading ? null : loaded.error;

  const visibleOptions = useMemo(() => {
    // Only show options that belong to the request currently on screen.
    const current = loaded.key === requestKey ? loaded.options : [];
    const term = search.trim().toLocaleLowerCase();
    if (!term) return current;
    return current.filter((item) =>
      item.name.toLocaleLowerCase().includes(term)
    );
  }, [loaded.key, loaded.options, requestKey, search]);

  const publish = useCallback(
    (next: HierarchySelection) => {
      setSelection(next);
      onChange?.(next);
    },
    [onChange]
  );

  /** Selecting a node clears everything below it in the cascade. */
  const select = (item: HierarchyNode) => {
    const next: HierarchySelection = {
      country: selection.country,
      province: selection.province,
      diocese: selection.diocese,
      deanery: selection.deanery,
      parish: selection.parish,
    };

    if (step === "country") {
      next.country = item;
    } else if (step === "province") {
      next.province = item as EcclesiasticalProvinceNode;
    } else if (step === "diocese") {
      next.diocese = item as DioceseNode;
    } else if (step === "deanery") {
      next.deanery = item;
    } else {
      next.parish = item as ParishNode;
    }

    publish(next);
    setSearch("");

    const index = STEPS.indexOf(step);
    if (index < STEPS.length - 1) setStep(STEPS[index + 1]);
  };

  const goBack = () => {
    const index = STEPS.indexOf(step);
    if (index > 0) {
      setSearch("");
      setStep(STEPS[index - 1]);
    }
  };

  const stepIndex = STEPS.indexOf(step);

  const breadcrumb = [
    selection.country?.name,
    selection.province?.name,
    selection.diocese?.name,
    selection.deanery?.name,
    selection.parish?.name,
  ]
    .filter(Boolean)
    .join("  ›  ");

  return (
    <View style={styles.wrapper}>
      <View style={styles.progressRow}>
        {STEPS.map((name, index) => (
          <View
            key={name}
            style={[
              styles.progressDot,
              index <= stepIndex && styles.progressDotActive,
            ]}
          />
        ))}
      </View>
      <Text style={styles.stepLabel}>
        STEP {stepIndex + 1} OF {STEPS.length} ·{" "}
        {STEP_TITLE[step].toUpperCase()}
      </Text>

      {breadcrumb ? <Text style={styles.breadcrumb}>{breadcrumb}</Text> : null}

      {stepIndex > 0 && (
        <Pressable
          accessibilityRole="button"
          onPress={goBack}
          style={styles.backButton}
        >
          <Text style={styles.backText}>‹  Back</Text>
        </Pressable>
      )}

      <TextInput
        accessibilityLabel={`Search ${STEP_PLURAL[step]}`}
        autoCapitalize="none"
        editable={!loading}
        onChangeText={setSearch}
        placeholder={`Search ${STEP_PLURAL[step]}`}
        style={styles.search}
        value={search}
      />

      {error ? (
        <View accessibilityRole="alert" style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => setAttempt((n) => n + 1)}
          >
            <Text style={styles.retry}>Try again</Text>
          </Pressable>
        </View>
      ) : null}

      {loading ? (
        <ActivityIndicator color="#0B6623" style={styles.loader} />
      ) : visibleOptions.length ? (
        visibleOptions.map((item) => {
          const chosen =
            step === "country"
              ? selection.country?.id === item.id
              : step === "province"
                ? selection.province?.id === item.id
                : step === "diocese"
                  ? selection.diocese?.id === item.id
                  : step === "deanery"
                    ? selection.deanery?.id === item.id
                    : selection.parish?.id === item.id;

          return (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: chosen }}
              key={item.id}
              onPress={() => select(item)}
              style={[styles.option, chosen && styles.optionSelected]}
            >
              <Text
                style={[styles.optionText, chosen && styles.optionTextSelected]}
              >
                {item.name}
              </Text>
              <Text style={styles.optionMeta}>{item.code}</Text>
              {chosen ? <Text style={styles.check}>Selected</Text> : null}
            </Pressable>
          );
        })
      ) : (
        <Text style={styles.empty}>
          {search
            ? "No matches. Try another search."
            : `No ${STEP_PLURAL[
                step
              ].toLocaleLowerCase()} are published at this step yet.`}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { width: "100%" },
  progressRow: { flexDirection: "row", gap: 6, marginBottom: 12 },
  progressDot: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#dfe5e0",
  },
  progressDotActive: { backgroundColor: "#0B6623" },
  stepLabel: {
    color: "#0B6623",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.7,
    marginBottom: 8,
  },
  breadcrumb: { color: "#637067", fontSize: 13, marginBottom: 14 },
  backButton: {
    alignSelf: "flex-start",
    paddingVertical: 8,
    marginBottom: 10,
  },
  backText: { color: "#0B6623", fontSize: 15, fontWeight: "700" },
  search: {
    borderColor: "#d8e0da",
    borderWidth: 1,
    borderRadius: 10,
    padding: 13,
    marginBottom: 14,
    backgroundColor: "#fff",
  },
  option: {
    padding: 15,
    backgroundColor: "#f4f7f4",
    marginBottom: 9,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#edf0ed",
  },
  optionSelected: { backgroundColor: "#e7f3e9", borderColor: "#0B6623" },
  optionText: { color: "#26332a", fontSize: 16 },
  optionTextSelected: { color: "#0B6623", fontWeight: "700" },
  optionMeta: { color: "#8a938c", fontSize: 11, marginTop: 3 },
  check: { color: "#0B6623", fontSize: 12, fontWeight: "700", marginTop: 4 },
  errorBox: {
    backgroundColor: "#fff1f0",
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  errorText: { color: "#982c20" },
  retry: { color: "#0B6623", fontWeight: "700", marginTop: 8 },
  loader: { marginVertical: 24 },
  empty: { color: "#68736b", textAlign: "center", padding: 18 },
});
