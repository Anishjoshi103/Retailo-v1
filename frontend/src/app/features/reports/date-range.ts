/** Date ranges for the report presets. Dates are plain `YYYY-MM-DD` strings in the device's calendar. */

export type Preset = 'today' | 'yesterday' | 'week' | 'month' | 'lastMonth';

export interface DateRange {
  readonly dateFrom?: string;
  readonly dateTo?: string;
}

export function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

function daysBefore(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() - days);
}

/**
 * The range for a preset. `today` returns no dates so the server decides what today is; the others are
 * worked out from `now` ("last 7 days" includes today).
 */
export function presetRange(preset: Preset, now: Date): DateRange {
  switch (preset) {
    case 'today':
      return {};
    case 'yesterday': {
      const day = toIsoDate(daysBefore(now, 1));
      return { dateFrom: day, dateTo: day };
    }
    case 'week':
      return { dateFrom: toIsoDate(daysBefore(now, 6)), dateTo: toIsoDate(now) };
    case 'month':
      return { dateFrom: toIsoDate(new Date(now.getFullYear(), now.getMonth(), 1)), dateTo: toIsoDate(now) };
    case 'lastMonth':
      // Day 0 of this month is the last day of the previous one, whatever its length.
      return { dateFrom: toIsoDate(new Date(now.getFullYear(), now.getMonth() - 1, 1)), dateTo: toIsoDate(new Date(now.getFullYear(), now.getMonth(), 0)) };
  }
}
