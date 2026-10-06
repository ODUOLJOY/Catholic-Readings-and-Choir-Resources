/**
 * A small, dependency-free calendar picker.
 *
 * The project does not ship a native date picker dependency, so this is a
 * self-contained month-view modal built from `View`/`Text`/`TouchableOpacity`.
 * It is constrained to Nairobi-local days (the app's calendar is Kenya-based)
 * and is intentionally minimal: it exists only to let a member jump to a date.
 */
import { useMemo, useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { MaxContentWidth } from "@/constants/theme";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

interface CalendarPickerProps {
  visible: boolean;
  date: Date;
  minDate?: Date;
  maxDate?: Date;
  onSelect: (date: Date) => void;
  onDismiss: () => void;
}

export function CalendarPicker({
  visible,
  date,
  minDate,
  maxDate,
  onSelect,
  onDismiss,
}: CalendarPickerProps) {
  // The month currently page-displayed in the grid.
  const [displayMonth, setDisplayMonth] = useState<Date>(date);

  const min = minDate ?? new Date(2000, 0, 1);
  const max = maxDate ?? new Date(
    new Date().getFullYear() + 5,
    new Date().getMonth(),
    new Date().getDate(),
  );

  const monthStart = useMemo(
    () => new Date(displayMonth.getFullYear(), displayMonth.getMonth(), 1),
    [displayMonth],
  );

  // The weekday (0=Sun) on which day 1 of the displayed month falls.
  const startWeekday = monthStart.getDay();

  // Total cells = leading blanks + days in month, padded to a full grid.
  const daysInMonth = new Date(
    monthStart.getFullYear(),
    monthStart.getMonth() + 1,
    0,
  ).getDate();

  const cells: { day: number; currentMonth: boolean }[] = [];
  for (let i = 0; i < startWeekday; i++) {
    cells.push({ day: 0, currentMonth: false });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, currentMonth: true });
  }
  while (cells.length % 7 !== 0) {
    cells.push({ day: 0, currentMonth: false });
  }

  const monthLabel = monthStart.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  function canMoveTo(target: Date): boolean {
    return target >= min && target <= max;
  }

  function moveMonth(step: number): void {
    const target = new Date(
      displayMonth.getFullYear(),
      displayMonth.getMonth() + step,
      1,
    );
    if (canMoveTo(target)) setDisplayMonth(target);
  }

  function isSameDay(a: Date, b: Date): boolean {
    return (
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate()
    );
  }

  function isToday(a: Date): boolean {
    return isSameDay(a, new Date());
  }

  function disabled(day: { day: number; currentMonth: boolean }): boolean {
    if (!day.currentMonth) return true;
    const candidate = new Date(
      monthStart.getFullYear(),
      monthStart.getMonth(),
      day.day,
    );
    return !canMoveTo(candidate);
  }

  function pick(day: number): void {
    const candidate = new Date(
      monthStart.getFullYear(),
      monthStart.getMonth(),
      day,
    );
    if (!canMoveTo(candidate)) return;
    onSelect(candidate);
  }

  return (
    <Modal
      animationType="fade"
      transparent
      visible={visible}
      onRequestClose={onDismiss}
    >
      <Pressable style={styles.backdrop} onPress={onDismiss} />
      <View style={styles.card}>
        <View style={styles.header}>
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Previous month"
            onPress={() => moveMonth(-1)}
            style={styles.navButton}
          >
            <Text style={styles.navText}>‹</Text>
          </TouchableOpacity>
          <Text style={styles.monthLabel} accessibilityRole="header">
            {monthLabel}
          </Text>
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Next month"
            onPress={() => moveMonth(1)}
            style={styles.navButton}
          >
            <Text style={styles.navText}>›</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.weekdayRow}>
          {WEEKDAYS.map((d) => (
            <Text key={d} style={styles.weekdayCell}>
              {d}
            </Text>
          ))}
        </View>

        <View style={styles.grid}>
          {cells.map((cell, index) => {
            const dayDate = new Date(
              monthStart.getFullYear(),
              monthStart.getMonth(),
              cell.day,
            );
            const off = disabled(cell);
            const selected = cell.currentMonth && isSameDay(dayDate, date);
            const today = cell.currentMonth && isToday(dayDate);
            return (
              <TouchableOpacity
                key={index}
                accessibilityRole="button"
                accessibilityLabel={
                  cell.currentMonth
                    ? `${dayDate.toLocaleDateString(undefined, {
                        weekday: "long",
                      })}, ${dayDate.toLocaleDateString(undefined, {
                        month: "long",
                        day: "numeric",
                        year: "numeric",
                      })}`
                    : "Outside current month"
                }
                accessibilityState={{ disabled: off, selected }}
                onPress={() => cell.currentMonth && !off && pick(cell.day)}
                disabled={off}
                style={[
                  styles.dayCell,
                  selected && styles.daySelected,
                  today && !selected && styles.dayToday,
                ]}
              >
                <Text
                  style={[
                    styles.dayText,
                    selected && styles.dayTextSelected,
                    off && styles.dayTextDimmed,
                  ]}
                >
                  {cell.day || ""}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Today"
          onPress={() => {
            const today = new Date();
            if (canMoveTo(today)) {
              setDisplayMonth(
                new Date(today.getFullYear(), today.getMonth(), 1),
              );
              onSelect(today);
            }
          }}
          style={styles.todayButton}
        >
          <Text style={styles.todayText}>Today</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  card: {
    position: "absolute",
    bottom: 64,
    left: 16,
    right: 16,
    backgroundColor: "#ffffff",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E5EAE6",
    overflow: "hidden",
    maxWidth: MaxContentWidth,
    alignSelf: "center",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#E5EAE6",
  },
  monthLabel: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0B6623",
    marginHorizontal: 12,
  },
  navButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F1F5F2",
  },
  navText: {
    fontSize: 20,
    color: "#0B6623",
    lineHeight: 20,
  },
  weekdayRow: {
    flexDirection: "row",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F2",
  },
  weekdayCell: {
    flex: 1,
    textAlign: "center",
    fontSize: 12,
    fontWeight: "600",
    color: "#6B7A70",
    textTransform: "uppercase",
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  dayCell: {
    width: "14.28%",
    aspectRatio: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  daySelected: {
    backgroundColor: "#0B6623",
    borderRadius: 20,
    margin: 4,
  },
  dayToday: {
    borderRadius: 20,
    margin: 4,
    borderWidth: 1,
    borderColor: "#0B6623",
  },
  dayText: {
    fontSize: 15,
    color: "#2D3A30",
  },
  dayTextSelected: {
    color: "#ffffff",
    fontWeight: "700",
  },
  dayTextDimmed: {
    color: "#D8E0DA",
  },
  todayButton: {
    paddingVertical: 10,
    alignItems: "center",
    borderTopWidth: 1,
    borderTopColor: "#F1F5F2",
  },
  todayText: {
    color: "#0B6623",
    fontWeight: "700",
    fontSize: 14,
  },
});
