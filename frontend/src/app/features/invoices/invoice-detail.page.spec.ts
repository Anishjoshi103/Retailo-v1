import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SalesApi } from '../pos/sales.api';
import { Sale } from '../pos/sales.models';
import { InvoiceDetailPage } from './invoice-detail.page';

function sale(overrides: Partial<Sale> = {}): Sale {
  return {
    id: 's-1', invoice_number: 'INV-MAIN-000001', invoice_date: '2026-11-09', branch_id: 'b-1', customer_name: 'Asha',
    taxable_total: '169.50', total_tax: '30.50', round_off: '0.00', grand_total: '200.00', created_at: '2026-11-09T10:00:00Z',
    seller_gstin: '27AAPFU0939F1ZV', seller_state_code: '27', place_of_supply_state_code: '27',
    cgst_total: '15.25', sgst_total: '15.25', igst_total: '0.00',
    lines: [{ id: 'sl-1', returned_quantity: '0.000', product_id: 'p-1', sku: 'RICE-1', name: 'Rice', hsn_code: '1006', unit: 'kg', quantity: '2.000', unit_price: '100.00', gst_rate: '18.00', taxable_value: '169.50', cgst_amount: '15.25', sgst_amount: '15.25', igst_amount: '0.00', line_total: '200.00' }],
    payments: [{ method: 'upi', amount: '200.00', reference: 'UPI-9' }],
    ...overrides,
  };
}

describe('InvoiceDetailPage', () => {
  let fixture: ComponentFixture<InvoiceDetailPage>;
  let salesApi: { get: ReturnType<typeof vi.fn> };

  const text = (): string => (fixture.nativeElement as HTMLElement).textContent ?? '';

  function create(): void {
    fixture = TestBed.createComponent(InvoiceDetailPage);
    fixture.detectChanges();
  }

  beforeEach(() => {
    salesApi = { get: vi.fn().mockReturnValue(of(sale())) };
    TestBed.configureTestingModule({
      imports: [InvoiceDetailPage],
      providers: [
        provideRouter([]),
        { provide: SalesApi, useValue: salesApi },
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: 's-1' })) } },
      ],
    });
  });

  it('loads the invoice named in the route and shows header, lines, totals and payments', () => {
    create();
    expect(salesApi.get).toHaveBeenCalledWith('s-1');
    const content = text();
    expect(content).toContain('INV-MAIN-000001');
    expect(content).toContain('27AAPFU0939F1ZV');
    expect(content).toContain('Asha');
    expect(content).toContain('Rice');
    expect(content).toContain('1006');
    expect(content).toContain('₹169.50');
    expect(content).toContain('CGST');
    expect(content).toContain('SGST');
    expect(content).toContain('₹200.00');
    expect(content).toContain('upi');
    expect(content).toContain('UPI-9');
  });

  it('shows IGST only when the invoice has any', () => {
    create();
    expect(text()).not.toContain('IGST');
    salesApi.get.mockReturnValue(of(sale({ igst_total: '30.50', cgst_total: '0.00', sgst_total: '0.00' })));
    create();
    expect(text()).toContain('IGST');
  });

  it('falls back for a walk-in customer and an unregistered seller', () => {
    salesApi.get.mockReturnValue(of(sale({ customer_name: '', seller_gstin: '' })));
    create();
    expect(text()).toContain('Walk-in');
    expect(text()).toContain('—');
  });

  it('says the invoice was not found on a 404', () => {
    salesApi.get.mockReturnValue(throwError(() => new ApiError('NOT_FOUND', 'Sale not found.', {}, null, 404)));
    create();
    expect(text()).toContain('Invoice not found');
    expect(text()).not.toContain('Print');
  });

  it('shows a retryable message for other failures', () => {
    salesApi.get.mockReturnValue(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    create();
    expect(text()).toContain('We could not load this invoice');
  });

  it('prints the invoice from the Print button', () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    create();
    const button = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('button')).find((b) => (b.textContent ?? '').includes('Print'));
    button?.click();
    expect(printSpy).toHaveBeenCalledTimes(1);
    printSpy.mockRestore();
  });
});
