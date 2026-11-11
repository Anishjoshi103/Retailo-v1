import { cumulativeShare, previewReturn, previewReturnLine, returnableMilli, ReturnLineInput } from './return-math';

function line(overrides: Partial<ReturnLineInput> = {}): ReturnLineInput {
  return { soldMilli: 2000, returnedBeforeMilli: 0, quantityMilli: 1000, taxablePaise: 16950, cgstPaise: 1525, sgstPaise: 1525, igstPaise: 0, ...overrides };
}

describe('return math', () => {
  it('shares an amount by cumulative quantity, rounding half-up', () => {
    expect(cumulativeShare(1000, 1000, 3000)).toBe(333);
    expect(cumulativeShare(1525, 1000, 2000)).toBe(763); // 7.625 -> 7.63
    expect(cumulativeShare(1000, 3000, 3000)).toBe(1000);
    expect(cumulativeShare(1000, 5000, 3000)).toBe(1000);
    expect(cumulativeShare(1000, 0, 3000)).toBe(0);
  });

  it('stays exact where floating point would lose precision', () => {
    // 999,999,999,999 x 500,000 is about 5e17, beyond Number's exact integer range (9e15).
    expect(cumulativeShare(999_999_999_999, 500_000, 1_000_000)).toBe(500_000_000_000);
    expect(cumulativeShare(99_999_999_999, 333, 1000)).toBe(33_300_000_000);
  });

  it('reports the quantity still returnable', () => {
    expect(returnableMilli(3000, 1500)).toBe(1500);
    expect(returnableMilli(3000, 3000)).toBe(0);
    expect(returnableMilli(3000, 4000)).toBe(0);
  });

  it('matches the server for returning one of two items', () => {
    const first = previewReturnLine(line());
    expect(first).toEqual({ taxablePaise: 8475, cgstPaise: 763, sgstPaise: 763, igstPaise: 0, totalPaise: 10001 });
    const second = previewReturnLine(line({ returnedBeforeMilli: 1000 }));
    expect(second).toEqual({ taxablePaise: 8475, cgstPaise: 762, sgstPaise: 762, igstPaise: 0, totalPaise: 9999 });
  });

  it('refunds the rupee-rounded total with a signed round-off', () => {
    expect(previewReturn([line()])).toEqual({ taxablePaise: 8475, taxPaise: 1526, exactPaise: 10001, refundPaise: 10000, roundOffPaise: -1 });
    expect(previewReturn([line({ returnedBeforeMilli: 1000 })])).toEqual({ taxablePaise: 8475, taxPaise: 1524, exactPaise: 9999, refundPaise: 10000, roundOffPaise: 1 });
  });

  it('refunds exactly the invoice total when every line is returned', () => {
    const rice = line({ soldMilli: 2000, quantityMilli: 2000 });
    const soap = line({ soldMilli: 3000, quantityMilli: 3000, taxablePaise: 9523, cgstPaise: 238, sgstPaise: 238 });
    expect(previewReturn([rice, soap])).toEqual({ taxablePaise: 26473, taxPaise: 3526, exactPaise: 29999, refundPaise: 30000, roundOffPaise: 1 });
  });

  it('adds up to the original line for any split of the quantity, never negative, CGST equal to SGST', () => {
    const splits: readonly (readonly number[])[] = [[1000, 1000, 1000], [500, 2500], [333, 333, 334], [1000, 2000, 1, 3999], [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]];
    const solds = [3000, 3000, 1000, 7000, 1000];
    splits.forEach((parts, index) => {
      const sold = solds[index];
      expect(parts.reduce((a, b) => a + b, 0)).toBe(sold);
      let before = 0;
      const sums = [0, 0, 0, 0];
      for (const quantityMilli of parts) {
        const preview = previewReturnLine({ soldMilli: sold, returnedBeforeMilli: before, quantityMilli, taxablePaise: 123457, cgstPaise: 5555, sgstPaise: 5555, igstPaise: 0 });
        before += quantityMilli;
        for (const value of [preview.taxablePaise, preview.cgstPaise, preview.sgstPaise, preview.igstPaise]) expect(value).toBeGreaterThanOrEqual(0);
        expect(preview.cgstPaise).toBe(preview.sgstPaise);
        sums[0] += preview.taxablePaise; sums[1] += preview.cgstPaise; sums[2] += preview.sgstPaise; sums[3] += preview.igstPaise;
      }
      expect(sums).toEqual([123457, 5555, 5555, 0]);
    });
  });

  it('reverses IGST for inter-state sales', () => {
    const first = previewReturnLine(line({ cgstPaise: 0, sgstPaise: 0, igstPaise: 3050 }));
    const second = previewReturnLine(line({ cgstPaise: 0, sgstPaise: 0, igstPaise: 3050, returnedBeforeMilli: 1000 }));
    expect(first.igstPaise + second.igstPaise).toBe(3050);
  });

  it('previews an empty return as zero', () => {
    expect(previewReturn([])).toEqual({ taxablePaise: 0, taxPaise: 0, exactPaise: 0, refundPaise: 0, roundOffPaise: 0 });
  });
});
