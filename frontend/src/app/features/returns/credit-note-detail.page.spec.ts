import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { CreditNoteDetailPage } from './credit-note-detail.page';
import { ReturnsApi } from './returns.api';
import { CreditNote } from './returns.models';

function note(overrides: Partial<CreditNote> = {}): CreditNote {
  return {
    id: 'cn-1', credit_note_number: 'CN-MAIN-000001', credit_note_date: '2026-11-10', sale_id: 's-1', invoice_number: 'INV-MAIN-000001',
    branch_id: 'b-1', reason: 'Damaged', customer_name: 'Asha', grand_total: '100.00', created_at: '2026-11-10T10:00:00Z',
    seller_gstin: '27AAPFU0939F1ZV', seller_state_code: '27', place_of_supply_state_code: '27',
    taxable_total: '84.75', cgst_total: '7.63', sgst_total: '7.63', igst_total: '0.00', total_tax: '15.26', round_off: '-0.01',
    refund_method: 'cash', refund_amount: '100.00',
    lines: [{ sale_line_id: 'sl-1', product_id: 'p-1', sku: 'RICE-1', name: 'Rice', hsn_code: '1006', unit: 'kg', quantity: '1.000', unit_price: '100.00', gst_rate: '18.00', taxable_value: '84.75', cgst_amount: '7.63', sgst_amount: '7.63', igst_amount: '0.00', line_total: '100.01' }],
    ...overrides,
  };
}

describe('CreditNoteDetailPage', () => {
  let fixture: ComponentFixture<CreditNoteDetailPage>;
  let returnsApi: { get: ReturnType<typeof vi.fn> };

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';

  function create(): void {
    fixture = TestBed.createComponent(CreditNoteDetailPage);
    fixture.detectChanges();
  }

  beforeEach(() => {
    returnsApi = { get: vi.fn().mockReturnValue(of(note())) };
    TestBed.configureTestingModule({
      imports: [CreditNoteDetailPage],
      providers: [
        provideRouter([]),
        { provide: ReturnsApi, useValue: returnsApi },
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: 'cn-1' })) } },
      ],
    });
  });

  it('shows the credit note, its reason, the original invoice, lines, totals and the cash refund', () => {
    create();
    expect(returnsApi.get).toHaveBeenCalledWith('cn-1');
    const content = text();
    expect(content).toContain('CN-MAIN-000001');
    expect(content).toContain('Reason: Damaged');
    expect(content).toContain('INV-MAIN-000001');
    expect(content).toContain('27AAPFU0939F1ZV');
    expect(content).toContain('Rice');
    expect(content).toContain('₹100.01');
    expect(content).toContain('CGST');
    expect(content).toContain('Cash refund');
    expect(content).toContain('₹100.00');
    const invoiceLink = Array.from(element().querySelectorAll('a')).find((a) => (a.textContent ?? '').includes('INV-MAIN-000001'));
    expect(invoiceLink?.getAttribute('href')).toBe('/gst/s-1');
  });

  it('shows IGST only when present and falls back for walk-in customers', () => {
    create();
    expect(text()).not.toContain('IGST');
    returnsApi.get.mockReturnValue(of(note({ igst_total: '15.26', cgst_total: '0.00', sgst_total: '0.00', customer_name: '' })));
    create();
    expect(text()).toContain('IGST');
    expect(text()).toContain('Walk-in');
  });

  it('says the credit note was not found on a 404', () => {
    returnsApi.get.mockReturnValue(throwError(() => new ApiError('NOT_FOUND', 'Credit note not found.', {}, null, 404)));
    create();
    expect(text()).toContain('Credit note not found');
    expect(text()).not.toContain('Print');
  });

  it('shows a retryable message for other failures', () => {
    returnsApi.get.mockReturnValue(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    create();
    expect(text()).toContain('We could not load this credit note');
  });

  it('prints from the Print button', () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    create();
    const button = Array.from(element().querySelectorAll('button')).find((b) => (b.textContent ?? '').includes('Print'));
    button?.click();
    expect(printSpy).toHaveBeenCalledTimes(1);
    printSpy.mockRestore();
  });
});
