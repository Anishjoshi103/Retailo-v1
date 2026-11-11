/**
 * Exact preview of a credit note, mirroring the server (`apps/sales/returns.py`).
 *
 * For each of taxable value, CGST, SGST and IGST, the amount returned so far is the original
 * line amount x (cumulative quantity returned / quantity sold), rounded half-up to paise. A
 * return is the difference between the running totals after and before it, so repeated
 * partial returns add up to the original line exactly and never go negative. The cash refund
 * is the exact total rounded half-up to the rupee, like the invoice it reverses.
 *
 * Amounts are integer paise and quantities integer milli-units; BigInt keeps the product
 * exact for any realistic bill. The server stays authoritative.
 */

/** Portion of `amountPaise` attributable to `returnedMilli` of `soldMilli`, rounded half-up. */
export function cumulativeShare(amountPaise: number, returnedMilli: number, soldMilli: number): number {
  if (returnedMilli >= soldMilli) return amountPaise;
  const amount = BigInt(amountPaise);
  const returned = BigInt(returnedMilli);
  const sold = BigInt(soldMilli);
  return Number((2n * amount * returned + sold) / (2n * sold));
}

/** Quantity (milli-units) that can still be returned from a line. */
export function returnableMilli(soldMilli: number, returnedMilli: number): number {
  return Math.max(0, soldMilli - returnedMilli);
}

export interface ReturnLineInput {
  readonly soldMilli: number;
  readonly returnedBeforeMilli: number;
  readonly quantityMilli: number;
  readonly taxablePaise: number;
  readonly cgstPaise: number;
  readonly sgstPaise: number;
  readonly igstPaise: number;
}

export interface ReturnLinePreview {
  readonly taxablePaise: number;
  readonly cgstPaise: number;
  readonly sgstPaise: number;
  readonly igstPaise: number;
  readonly totalPaise: number;
}

export function previewReturnLine(line: ReturnLineInput): ReturnLinePreview {
  const after = line.returnedBeforeMilli + line.quantityMilli;
  const part = (amount: number): number =>
    cumulativeShare(amount, after, line.soldMilli) - cumulativeShare(amount, line.returnedBeforeMilli, line.soldMilli);
  const taxablePaise = part(line.taxablePaise);
  const cgstPaise = part(line.cgstPaise);
  const sgstPaise = part(line.sgstPaise);
  const igstPaise = part(line.igstPaise);
  return { taxablePaise, cgstPaise, sgstPaise, igstPaise, totalPaise: taxablePaise + cgstPaise + sgstPaise + igstPaise };
}

export interface ReturnPreview {
  readonly taxablePaise: number;
  readonly taxPaise: number;
  /** Sum of the line totals before rupee rounding. */
  readonly exactPaise: number;
  /** Cash to hand back: exact total rounded half-up to the nearest rupee. */
  readonly refundPaise: number;
  /** refund - exact; may be negative. */
  readonly roundOffPaise: number;
}

export function previewReturn(lines: readonly ReturnLineInput[]): ReturnPreview {
  const parts = lines.map(previewReturnLine);
  const taxablePaise = parts.reduce((sum, part) => sum + part.taxablePaise, 0);
  const taxPaise = parts.reduce((sum, part) => sum + part.cgstPaise + part.sgstPaise + part.igstPaise, 0);
  const exactPaise = taxablePaise + taxPaise;
  const refundPaise = Math.floor((exactPaise + 50) / 100) * 100;
  return { taxablePaise, taxPaise, exactPaise, refundPaise, roundOffPaise: refundPaise - exactPaise };
}
