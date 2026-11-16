import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { DeliveryDetailPage } from './delivery-detail.page';
import { PurchasesApi } from './purchases.api';
import { ReceiptDetail } from './purchases.models';

function detail(overrides: Partial<ReceiptDetail> = {}): ReceiptDetail {
  return {
    id: 'r-1', branch_id: 'b-1', supplier_id: 's-1', supplier_name: 'Agro Foods', supplier_invoice_number: 'AF-99', received_at: '2026-11-10T09:30:00Z',
    line_count: 2, total_cost: '114.98',
    lines: [
      { id: 'l-1', product_id: 'p-1', sku: 'RICE-1', name: 'Rice', unit: 'kg', quantity: '3.000', unit_cost: '33.33', line_total: '99.99' },
      { id: 'l-2', product_id: 'p-2', sku: 'SOAP-1', name: 'Soap', unit: 'each', quantity: '0.333', unit_cost: '45.00', line_total: '14.99' },
    ],
    ...overrides,
  };
}

describe('DeliveryDetailPage', () => {
  let fixture: ComponentFixture<DeliveryDetailPage>;
  let api: { receipt: ReturnType<typeof vi.fn> };

  const text = (): string => (fixture.nativeElement as HTMLElement).textContent ?? '';

  function create(): void {
    fixture = TestBed.createComponent(DeliveryDetailPage);
    fixture.detectChanges();
  }

  beforeEach(() => {
    api = { receipt: vi.fn().mockReturnValue(of(detail())) };
    TestBed.configureTestingModule({
      imports: [DeliveryDetailPage],
      providers: [provideRouter([]), { provide: PurchasesApi, useValue: api }, { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: 'r-1' })) } }],
    });
  });

  it('shows the supplier, invoice number, date, lines and total cost', () => {
    create();
    expect(api.receipt).toHaveBeenCalledWith('r-1');
    const content = text();
    expect(content).toContain('Agro Foods');
    expect(content).toContain('AF-99');
    expect(content).toContain('2026-11-10');
    expect(content).toContain('Rice');
    expect(content).toContain('RICE-1');
    expect(content).toContain('3.000 kg');
    expect(content).toContain('₹33.33');
    expect(content).toContain('₹99.99');
    expect(content).toContain('₹14.99');
    expect(content).toContain('₹114.98');
    expect((fixture.nativeElement as HTMLElement).querySelector('a.back')?.getAttribute('href')).toBe('/purchases/history');
  });

  it('shows a dash when there is no supplier invoice number', () => {
    api.receipt.mockReturnValue(of(detail({ supplier_invoice_number: '' })));
    create();
    expect(text()).toContain('—');
  });

  it('says the delivery was not found on a 404', () => {
    api.receipt.mockReturnValue(throwError(() => new ApiError('NOT_FOUND', 'Receipt not found.', {}, null, 404)));
    create();
    expect(text()).toContain('Delivery not found');
  });

  it('shows a retryable message for other failures', () => {
    api.receipt.mockReturnValue(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    create();
    expect(text()).toContain('We could not load this delivery');
  });
});
