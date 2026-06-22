import { readingsDB } from "../data/readings";
import { feastDays } from "../liturgy/feastDays";
import {
  getLiturgicalYear,
  getSeason,
} from "../liturgy/calendarEngine";

export function getTodayReadings(
  language: "English" | "Swahili"
) {
  const today = new Date()
    .toISOString()
    .split("T")[0];

  const year = getLiturgicalYear();

  const season = getSeason();

  const feast = feastDays[today];

  const readings = readingsDB
    .filter(
      (r) =>
        r.language === language &&
        r.date === today
    )
    .map((r) => ({
      ...r,
      year,
      season,
      feastName: feast,
    }));

  return readings;
}