import { branchCodeProblem, GST_STATES, isValidGstinFormat, stateName } from './gst-states';

describe('GST helpers', () => {
  it('lists each state code once, in the range the API accepts', () => {
    const codes = GST_STATES.map((state) => state.code);
    expect(new Set(codes).size).toBe(codes.length);
    for (const code of codes) expect(['97', '99'].includes(code) || (Number(code) >= 1 && Number(code) <= 38), code).toBe(true);
    expect(codes).toContain('27');
  });

  it('names a state from its code', () => {
    expect(stateName('27')).toBe('Maharashtra');
    expect(stateName('29')).toBe('Karnataka');
    expect(stateName('00')).toBe('');
  });

  it('accepts a well-formed GSTIN and rejects malformed ones', () => {
    expect(isValidGstinFormat('27AAPFU0939F1ZV')).toBe(true);
    for (const bad of ['', '27aapfu0939f1zv', '27AAPFU0939F1XV', '27AAPFU0939F1Z', '7AAPFU0939F1ZV', 'NOT-A-GSTIN', '27AAPFU0939F0ZV']) {
      expect(isValidGstinFormat(bad), bad).toBe(false);
    }
  });

  it('flags branch codes that cannot form a 16-character invoice number', () => {
    expect(branchCodeProblem('MAIN')).toBe('');
    expect(branchCodeProblem('NORTH')).toBe('');
    expect(branchCodeProblem('NORTH1')).toContain('6 characters');
    expect(branchCodeProblem('A B')).toContain('only letters');
  });
});
