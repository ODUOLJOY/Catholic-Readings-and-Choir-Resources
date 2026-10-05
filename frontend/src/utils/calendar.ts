const KENYA_TIME_ZONE = "Africa/Nairobi";

function toDateString(date: Date): string {
	return date.toISOString().slice(0, 10);
}

export function kenyaDateString(date: Date = new Date()): string {
	const parts = new Intl.DateTimeFormat("en-CA", {
		timeZone: KENYA_TIME_ZONE,
		year: "numeric",
		month: "2-digit",
		day: "2-digit",
	}).formatToParts(date);
	const part = (type: string) => parts.find((value) => value.type === type)?.value;
	return `${part("year")}-${part("month")}-${part("day")}`;
}

export function shiftCalendarDate(dateString: string, days: number): string {
	const [year, month, day] = dateString.split("-").map(Number);
	return toDateString(new Date(Date.UTC(year, month - 1, day + days, 12)));
}

export function formatKenyaDate(dateString: string): string {
	const [year, month, day] = dateString.split("-").map(Number);
	const date = new Date(Date.UTC(year, month - 1, day, 12));
	return new Intl.DateTimeFormat(undefined, {
		timeZone: KENYA_TIME_ZONE,
		weekday: "short",
		day: "numeric",
		month: "short",
		year: "numeric",
	}).format(date);
}

export function kenyaMonthRange(date: Date = new Date()): {
	startDate: string;
	endDate: string;
} {
	const [year, month] = kenyaDateString(date).split("-").map(Number);
	return {
		startDate: toDateString(new Date(Date.UTC(year, month - 1, 1, 12))),
		endDate: toDateString(new Date(Date.UTC(year, month, 0, 12))),
	};
}

/**
 * The Nairobi month a date falls in, as `YYYY-MM`.
 *
 * Comparing this string is how the calendar screen decides whether the member is
 * looking at the present month, without re-deriving the timezone on every render.
 */
export function kenyaMonthKey(date: Date = new Date()): string {
	return kenyaDateString(date).slice(0, 7);
}

/**
 * Move a `YYYY-MM` month key by `months`, crossing year boundaries.
 *
 * `Date.UTC` normalizes an out-of-range month (`month - 1 + months` of `13`),
 * so December plus one becomes January of the next year without a special case.
 * The 12:00 time-of-day keeps the UTC date stable everywhere, which is what
 * `toDateString` needs to avoid an off-by-one near month ends.
 */
export function shiftKenyaMonth(monthKey: string, months: number): string {
	const [year, month] = monthKey.split("-").map(Number);
	if (!Number.isFinite(year) || !Number.isFinite(month)) {
		return monthKey;
	}
	const shifted = new Date(Date.UTC(year, month - 1 + months, 1, 12));
	return `${shifted.getUTCFullYear()}-${String(shifted.getUTCMonth() + 1).padStart(2, "0")}`;
}

/** Human-readable label for a `YYYY-MM` month key, e.g. `March 2026`. */
export function kenyaMonthLabel(monthKey: string): string {
	const [year, month] = monthKey.split("-").map(Number);
	if (!Number.isFinite(year) || !Number.isFinite(month)) {
		return monthKey;
	}
	return new Intl.DateTimeFormat(undefined, {
		timeZone: KENYA_TIME_ZONE,
		month: "long",
		year: "numeric",
	}).format(new Date(Date.UTC(year, month - 1, 1, 12)));
}
