import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { PosPage } from './pos.page';
import { SalesApi } from './sales.api';
import { Sale } from './sales.models';

const rice = { id: 'p-rice', sku: 'RICE-1', barcode: '8901', name: 'Rice', unit: 'kg', gst_rate: '18.00', selling_price: '100.00', is_active: true };
const soap = { id: 'p-soap', sku: 'SOAP-1', barcode: null, name: 'Soap', unit: 'each', gst_rate: '5.00', selling_price: '33.33', is_active: true };

function saleResponse(overrides: Partial<Sale> = {}): Sale {
  return {
    id: 's-1', invoice_number: 'INV-MAIN-000001', invoice_date: '2026-11-09', branch_id: 'b-1', customer_name: '',
    taxable_total: '169.50', total_tax: '30.50', round_off: '0.00', grand_total: '200.00', created_at: '2026-11-09T10:00:00Z',
    seller_gstin: '', seller_state_code: '27', place_of_supply_state_code: '27', cgst_total: '15.25', sgst_total: '15.25', igst_total: '0.00',
    lines: [], payments: [{ method: 'cash', amount: '200.00', reference: '' }], ...overrides,
  };
}

describe('PosPage', () => {
  let fixture: ComponentFixture<PosPage>;
  let page: PosPage;
  let api: { get: ReturnType<typeof vi.fn> };
  let salesApi: { create: ReturnType<typeof vi.fn> };
  let roles: ReturnType<typeof signal<readonly string[]>>;

  const text = (): string => (fixture.nativeElement as HTMLElement).textContent ?? '';
  const refresh = (): void => fixture.detectChanges();
  const button = (label: string): HTMLButtonElement => {
    const found = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('button')).find((b) => (b.textContent ?? '').includes(label));
    if (!found) throw new Error(`No button "${label}"`);
    return found;
  };

  beforeEach(() => {
    api = { get: vi.fn().mockReturnValue(of([])) };
    salesApi = { create: vi.fn().mockReturnValue(of(saleResponse())) };
    roles = signal<readonly string[]>(['cashier']);
    TestBed.configureTestingModule({
      imports: [PosPage],
      providers: [
        provideRouter([]),
        { provide: ApiClient, useValue: api },
        { provide: SalesApi, useValue: salesApi },
        { provide: SessionContextService, useValue: { roles, selectedBranchId: signal('b-1') } },
      ],
    });
    fixture = TestBed.createComponent(PosPage);
    page = fixture.componentInstance;
    refresh();
  });

  it('searches active products and adds a result to the cart', () => {
    api.get.mockReturnValue(of([rice, soap]));
    page.searchText.set('rice');
    page.search();
    refresh();
    expect(api.get).toHaveBeenCalledWith('products', expect.objectContaining({ params: expect.anything() }));
    expect(text()).toContain('Soap');
    page.addProduct(rice);
    refresh();
    expect(text()).toContain('Current sale');
    expect(page.totals().grandTotalPaise).toBe(10000);
    expect(text()).toContain('₹100.00');
  });

  it('adds an exact SKU or barcode match straight to the cart', () => {
    api.get.mockReturnValue(of([rice]));
    page.searchText.set('8901');
    page.search();
    refresh();
    expect(page.cart().map((item) => item.product.id)).toEqual(['p-rice']);
    expect(page.results()).toEqual([]);
    expect(page.searchText()).toBe('');
  });

  it('adding the same product again increases its quantity', () => {
    page.addProduct(rice);
    page.addProduct(rice);
    expect(page.cart()).toHaveLength(1);
    expect(page.cart()[0].quantityText).toBe('2.000');
    expect(page.totals().grandTotalPaise).toBe(20000);
  });

  it('prices exactly like the server and fills the single payment with the total', () => {
    page.addProduct(soap);
    page.setQuantity('p-soap', '3');
    refresh();
    expect(page.totals()).toEqual({ exactPaise: 9999, grandTotalPaise: 10000, roundOffPaise: 1 });
    expect(page.payments()[0].amountText).toBe('100.00');
    expect(page.canSubmit()).toBe(true);
  });

  it('blocks completion while an item quantity is invalid', () => {
    page.addProduct(rice);
    page.setQuantity('p-rice', '0');
    refresh();
    expect(page.cartValid()).toBe(false);
    expect(page.canSubmit()).toBe(false);
    expect(text()).toContain('Enter a quantity above zero');
  });

  it('supports split payments and only allows completion when they match the total', () => {
    page.addProduct(rice);
    page.setQuantity('p-rice', '2');
    page.setPaymentAmount(page.payments()[0].id, '150');
    expect(page.remainingPaise()).toBe(5000);
    expect(page.canSubmit()).toBe(false);
    page.addPayment();
    expect(page.payments()[1].amountText).toBe('50.00');
    page.setPaymentMethod(page.payments()[1].id, 'upi');
    expect(page.remainingPaise()).toBe(0);
    expect(page.canSubmit()).toBe(true);
    page.setPaymentAmount(page.payments()[1].id, '60');
    refresh();
    expect(page.canSubmit()).toBe(false);
    expect(text()).toContain('over the total');
  });

  it('submits the sale with decimal strings and shows the invoice number', () => {
    page.addProduct(rice);
    page.setQuantity('p-rice', '2');
    page.customerName.set('  Asha  ');
    page.submit();
    refresh();
    expect(salesApi.create).toHaveBeenCalledTimes(1);
    const [request, key] = salesApi.create.mock.calls[0];
    expect(request).toEqual({
      branch_id: 'b-1', customer_name: 'Asha',
      lines: [{ product_id: 'p-rice', quantity: '2.000' }],
      payments: [{ method: 'cash', amount: '200.00' }],
    });
    expect(typeof key).toBe('string');
    expect(text()).toContain('Sale complete');
    expect(text()).toContain('INV-MAIN-000001');
    const link = (fixture.nativeElement as HTMLElement).querySelector('a.view-invoice');
    expect(link?.getAttribute('href')).toBe('/gst/s-1');
  });

  it('retries a failed sale with the same idempotency key, and a changed sale with a new one', () => {
    salesApi.create.mockReturnValue(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    page.addProduct(rice);
    page.submit();
    page.submit();
    const [, firstKey] = salesApi.create.mock.calls[0];
    const [, retryKey] = salesApi.create.mock.calls[1];
    expect(retryKey).toBe(firstKey);
    page.setQuantity('p-rice', '2');
    page.submit();
    const [, changedKey] = salesApi.create.mock.calls[2];
    expect(changedKey).not.toBe(firstKey);
  });

  it('uses a new key for the next sale after a success', () => {
    page.addProduct(rice);
    page.submit();
    page.newSale();
    page.addProduct(rice);
    page.submit();
    expect(salesApi.create.mock.calls[1][1]).not.toBe(salesApi.create.mock.calls[0][1]);
  });

  it('shows server validation details and a safe-retry message for network failures', () => {
    page.addProduct(rice);
    salesApi.create.mockReturnValueOnce(throwError(() => new ApiError('VALIDATION_ERROR', 'Invalid', { lines: ['Insufficient stock for RICE-1: 0 on hand, 1 requested.'] }, null, 400)));
    page.submit();
    refresh();
    expect(text()).toContain('Insufficient stock for RICE-1');
    salesApi.create.mockReturnValueOnce(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    page.submit();
    refresh();
    expect(text()).toContain('will not be billed twice');
    expect(page.completedSale()).toBeNull();
  });

  it('offers the stock override only to managers and sends it only when ticked', () => {
    page.addProduct(rice);
    refresh();
    expect(text()).not.toContain('manager override');
    page.allowBelowStock.set(true);
    page.submit();
    expect(salesApi.create.mock.calls[0][0]).not.toHaveProperty('allow_negative_stock');

    roles.set(['manager']);
    page.newSale();
    page.addProduct(rice);
    refresh();
    expect(text()).toContain('manager override');
    page.submit();
    expect(salesApi.create.mock.calls[1][0]).not.toHaveProperty('allow_negative_stock');
    page.newSale();
    page.addProduct(rice);
    page.allowBelowStock.set(true);
    page.submit();
    expect(salesApi.create.mock.calls[2][0].allow_negative_stock).toBe(true);
  });

  it('does not submit twice while a request is in flight', () => {
    page.addProduct(rice);
    page.submitting.set(true);
    page.submit();
    expect(salesApi.create).not.toHaveBeenCalled();
  });

  it('starts a fresh sale from the receipt', () => {
    page.addProduct(rice);
    page.submit();
    refresh();
    button('New sale').click();
    refresh();
    expect(page.completedSale()).toBeNull();
    expect(page.cart()).toEqual([]);
    expect(text()).toContain('No items yet');
  });
});
