/** GST state and union territory codes, as accepted by the API (`01`-`38`, `97`, `99`). */
export interface GstState {
  readonly code: string;
  readonly name: string;
}

export const GST_STATES: readonly GstState[] = [
  { code: '01', name: 'Jammu & Kashmir' }, { code: '02', name: 'Himachal Pradesh' }, { code: '03', name: 'Punjab' },
  { code: '04', name: 'Chandigarh' }, { code: '05', name: 'Uttarakhand' }, { code: '06', name: 'Haryana' },
  { code: '07', name: 'Delhi' }, { code: '08', name: 'Rajasthan' }, { code: '09', name: 'Uttar Pradesh' },
  { code: '10', name: 'Bihar' }, { code: '11', name: 'Sikkim' }, { code: '12', name: 'Arunachal Pradesh' },
  { code: '13', name: 'Nagaland' }, { code: '14', name: 'Manipur' }, { code: '15', name: 'Mizoram' },
  { code: '16', name: 'Tripura' }, { code: '17', name: 'Meghalaya' }, { code: '18', name: 'Assam' },
  { code: '19', name: 'West Bengal' }, { code: '20', name: 'Jharkhand' }, { code: '21', name: 'Odisha' },
  { code: '22', name: 'Chhattisgarh' }, { code: '23', name: 'Madhya Pradesh' }, { code: '24', name: 'Gujarat' },
  { code: '26', name: 'Dadra & Nagar Haveli and Daman & Diu' }, { code: '27', name: 'Maharashtra' },
  { code: '29', name: 'Karnataka' }, { code: '30', name: 'Goa' }, { code: '31', name: 'Lakshadweep' },
  { code: '32', name: 'Kerala' }, { code: '33', name: 'Tamil Nadu' }, { code: '34', name: 'Puducherry' },
  { code: '35', name: 'Andaman & Nicobar Islands' }, { code: '36', name: 'Telangana' }, { code: '37', name: 'Andhra Pradesh' },
  { code: '38', name: 'Ladakh' }, { code: '97', name: 'Other Territory' }, { code: '99', name: 'Centre Jurisdiction' },
];

export function stateName(code: string): string {
  return GST_STATES.find((state) => state.code === code)?.name ?? '';
}

/** Same shape the API enforces: 2-digit state, 5 letters, 4 digits, a letter, entity, `Z`, check character. */
const GSTIN_PATTERN = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

export function isValidGstinFormat(gstin: string): boolean {
  return GSTIN_PATTERN.test(gstin);
}

/** Invoice numbers are `INV-<code>-<6 digits>` and GST allows 16 characters, so the code is at most 5. */
export const MAX_INVOICE_BRANCH_CODE_LENGTH = 5;

export function branchCodeProblem(code: string): string {
  if (!/^[A-Za-z0-9/-]+$/.test(code)) return 'The branch code may contain only letters, digits, hyphen and slash to issue invoices.';
  if (code.length > MAX_INVOICE_BRANCH_CODE_LENGTH) return `The branch code is ${code.length} characters; invoices need ${MAX_INVOICE_BRANCH_CODE_LENGTH} or fewer.`;
  return '';
}
