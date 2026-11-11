/**
 * Exact money and quantity arithmetic for the billing screen.
 *
 * Amounts are integer paise and quantities integer milli-units, so no floating-point
 * rounding can creep in. The rules mirror the server (`apps/sales/pricing.py`):
 * a line's gross amount is quantity x tax-inclusive price rounded half-up to paise, and
 * the invoice total is the sum of lines rounded half-up to the nearest rupee. The server
 * stays authoritative; this only previews the amount the customer will be billed.
 */

const MONEY_PATTERN = /^\d+(\.\d{1,2})?$/;
const QUANTITY_PATTERN = /^\d+(\.\d{1,3})?$/;

/** Parse a non-negative decimal string such as "42.5" into paise, or null if invalid. */
export function parseMoney(value: string): number | null {
  const text = value.trim();
  if (!MONEY_PATTERN.test(text)) return null;
  const [rupees, fraction = ''] = text.split('.');
  return Number(rupees) * 100 + Number(fraction.padEnd(2, '0'));
}

/** Parse a positive quantity with up to 3 decimals into milli-units, or null if invalid. */
export function parseQuantity(value: string): number | null {
  const text = value.trim();
  if (!QUANTITY_PATTERN.test(text)) return null;
  const [whole, fraction = ''] = text.split('.');
  const milli = Number(whole) * 1000 + Number(fraction.padEnd(3, '0'));
  return milli > 0 ? milli : null;
}

/** Format paise as a two-decimal string, e.g. 10040 -> "100.40", -40 -> "-0.40". */
export function formatMoney(paise: number): string {
  const sign = paise < 0 ? '-' : '';
  const abs = Math.abs(paise);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, '0')}`;
}

/** Format paise as rupees with the sign in front, e.g. 5 -> "₹0.05", -40 -> "-₹0.40". */
export function formatRupees(paise: number): string {
  return `${paise < 0 ? '-' : ''}₹${formatMoney(Math.abs(paise))}`;
}

/** Format milli-units as a three-decimal quantity string, e.g. 2000 -> "2.000". */
export function formatQuantity(milli: number): string {
  return `${Math.floor(milli / 1000)}.${String(milli % 1000).padStart(3, '0')}`;
}

/** Gross amount of a line in paise: quantity (milli) x price (paise), rounded half-up. */
export function lineGross(pricePaise: number, quantityMilli: number): number {
  return Math.floor((pricePaise * quantityMilli + 500) / 1000);
}

export interface CartLinePrice {
  readonly pricePaise: number;
  readonly quantityMilli: number;
}

export interface CartTotals {
  /** Sum of line gross amounts, before rupee rounding. */
  readonly exactPaise: number;
  /** Amount to collect: exact total rounded half-up to the nearest rupee. */
  readonly grandTotalPaise: number;
  /** grandTotal - exact; may be negative. */
  readonly roundOffPaise: number;
}

export function priceCart(lines: readonly CartLinePrice[]): CartTotals {
  const exactPaise = lines.reduce((sum, line) => sum + lineGross(line.pricePaise, line.quantityMilli), 0);
  const grandTotalPaise = Math.floor((exactPaise + 50) / 100) * 100;
  return { exactPaise, grandTotalPaise, roundOffPaise: grandTotalPaise - exactPaise };
}
