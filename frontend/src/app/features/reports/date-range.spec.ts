import { presetRange, toIsoDate } from './date-range';

describe('report date ranges', () => {
  const now = new Date(2026, 10, 16, 14, 30); // 16 November 2026

  it('formats a date as YYYY-MM-DD with leading zeros', () => {
    expect(toIsoDate(new Date(2026, 0, 5))).toBe('2026-01-05');
    expect(toIsoDate(new Date(2026, 11, 31))).toBe('2026-12-31');
  });

  it('leaves today to the server', () => {
    expect(presetRange('today', now)).toEqual({});
  });

  it('works out yesterday, the last 7 days and the month so far', () => {
    expect(presetRange('yesterday', now)).toEqual({ dateFrom: '2026-11-15', dateTo: '2026-11-15' });
    expect(presetRange('week', now)).toEqual({ dateFrom: '2026-11-10', dateTo: '2026-11-16' });
    expect(presetRange('month', now)).toEqual({ dateFrom: '2026-11-01', dateTo: '2026-11-16' });
  });

  it('crosses month and year boundaries correctly', () => {
    const newYear = new Date(2027, 0, 3);
    expect(presetRange('yesterday', newYear)).toEqual({ dateFrom: '2027-01-02', dateTo: '2027-01-02' });
    expect(presetRange('week', newYear)).toEqual({ dateFrom: '2026-12-28', dateTo: '2027-01-03' });
    expect(presetRange('yesterday', new Date(2026, 2, 1))).toEqual({ dateFrom: '2026-02-28', dateTo: '2026-02-28' });
    expect(presetRange('yesterday', new Date(2028, 2, 1))).toEqual({ dateFrom: '2028-02-29', dateTo: '2028-02-29' });
  });

  it('works out the whole of last month, whatever its length, including across a year', () => {
    expect(presetRange('lastMonth', now)).toEqual({ dateFrom: '2026-10-01', dateTo: '2026-10-31' });
    expect(presetRange('lastMonth', new Date(2026, 2, 10))).toEqual({ dateFrom: '2026-02-01', dateTo: '2026-02-28' });
    expect(presetRange('lastMonth', new Date(2028, 2, 10))).toEqual({ dateFrom: '2028-02-01', dateTo: '2028-02-29' });
    expect(presetRange('lastMonth', new Date(2027, 0, 5))).toEqual({ dateFrom: '2026-12-01', dateTo: '2026-12-31' });
    expect(presetRange('lastMonth', new Date(2026, 4, 31))).toEqual({ dateFrom: '2026-04-01', dateTo: '2026-04-30' });
  });

  it('starts the month on the first even when today is the first', () => {
    expect(presetRange('month', new Date(2026, 10, 1))).toEqual({ dateFrom: '2026-11-01', dateTo: '2026-11-01' });
  });
});
