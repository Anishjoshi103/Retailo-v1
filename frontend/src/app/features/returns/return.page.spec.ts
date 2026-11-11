import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SalesApi } from '../pos/sales.api';
import { Sale } from '../pos/sales.models';
import { ReturnPage } from './return.page';
import { ReturnsApi } from './returns.api';

const riceLine = { id: 'sl-rice', product_id: 'p-rice', sku: 'RICE-1', name: 'Rice', hsn_code: '1006', unit: 'kg', quantity: '2.000', returned_quantity: '0.000', unit_price: '100.00', gst_rate: '18.00', taxable_value: '169.50', cgst_amount: '15.25', sgst_amount: '15.25', igst_amount: '0.00', line_total: '200.00' };
const soapLine = { id: 'sl-soap', product_id: 'p-soap', sku: 'SOAP-1', name: 'Soap', hsn_code: '', unit: 'each', quantity: '3.000', returned_quantity: '0.000', unit_price: '33.33', gst_rate: '5.00', taxable_value: '95.23', cgst_amount: '2.38', sgst_amount: '2.38', igst_amount: '0.00', line_total: '99.99' };

function sale(overrides: Partial<Sale> = {}): Sale {
  return {
    id: 's-1', invoice_number: 'INV-MAIN-000001', invoice_date: '2026-11-09', branch_id: 'b-1', customer_name: '',
    taxable_total: '264.73', total_tax: '35.26', round_off: '0.01', grand_total: '300.00', created_at: '2026-11-09T10:00:00Z',
    seller_gstin: '', seller_state_code: '27', place_of_supply_state_code: '27', cgst_total: '17.63', sgst_total: '17.63', igst_total: '0.00',
    lines: [riceLine, soapLine], payments: [], ...overrides,
  };
}

describe('ReturnPage', () => {
  let fixture: ComponentFixture<ReturnPage>;
  let page: ReturnPage;
  let salesApi: { get: ReturnType<typeof vi.fn> };
  let returnsApi: { create: ReturnType<typeof vi.fn> };
  let navigate: ReturnType<typeof vi.fn>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(ReturnPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    salesApi = { get: vi.fn().mockReturnValue(of(sale())) };
    returnsApi = { create: vi.fn().mockReturnValue(of({ id: 'cn-1' })) };
    TestBed.configureTestingModule({
      imports: [ReturnPage],
      providers: [
        provideRouter([]),
        { provide: SalesApi, useValue: salesApi },
        { provide: ReturnsApi, useValue: returnsApi },
        { provide: ActivatedRoute, useValue: { paramMap: of(convertToParamMap({ id: 's-1' })) } },
      ],
    });
    navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true) as unknown as ReturnType<typeof vi.fn>;
  });

  it('loads the invoice and shows each line with what was sold, returned and can still come back', () => {
    salesApi.get.mockReturnValue(of(sale({ lines: [riceLine, { ...soapLine, returned_quantity: '3.000' }] })));
    create();
    expect(salesApi.get).toHaveBeenCalledWith('s-1');
    expect(text()).toContain('Return items from INV-MAIN-000001');
    expect(text()).toContain('sold 2.000 kg');
    expect(text()).toContain('Fully returned');
    expect(page.lines().map((state) => state.returnableMilli)).toEqual([2000, 0]);
  });

  it('flags an invalid quantity or one above what can still be returned, and blocks submitting', () => {
    create();
    page.setReason('Damaged');
    page.setQuantity('sl-rice', '3');
    refresh();
    expect(text()).toContain('Only 2.000 can still be returned.');
    expect(page.canSubmit()).toBe(false);
    page.setQuantity('sl-rice', 'abc');
    refresh();
    expect(text()).toContain('Enter a quantity above zero');
    expect(page.canSubmit()).toBe(false);
    page.setQuantity('sl-rice', '1');
    expect(page.canSubmit()).toBe(true);
  });

  it('takes into account what was already returned', () => {
    salesApi.get.mockReturnValue(of(sale({ lines: [{ ...riceLine, returned_quantity: '1.500' }] })));
    create();
    page.setQuantity('sl-rice', '1');
    expect(page.lines()[0].error).toBe('Only 0.500 can still be returned.');
  });

  it('fills quantities with All, Return everything and Clear', () => {
    create();
    page.returnAll(page.lines()[0]);
    expect(page.quantities()['sl-rice']).toBe('2.000');
    page.clearQuantities();
    page.returnEverything();
    expect(page.quantities()).toEqual({ 'sl-rice': '2.000', 'sl-soap': '3.000' });
    page.clearQuantities();
    expect(page.quantities()).toEqual({});
  });

  it('previews the cash refund exactly as the server will price it', () => {
    create();
    page.setQuantity('sl-rice', '1');
    refresh();
    expect(page.preview()).toEqual({ taxablePaise: 8475, taxPaise: 1526, exactPaise: 10001, refundPaise: 10000, roundOffPaise: -1 });
    expect(text()).toContain('₹100.00');
    expect(text()).toContain('-₹0.01');
  });

  it('refunds exactly the invoice total when everything is returned', () => {
    create();
    page.returnEverything();
    expect(page.preview().refundPaise).toBe(30000);
    expect(page.preview().roundOffPaise).toBe(1);
  });

  it('needs a reason, and a quick reason fills it in', () => {
    create();
    page.setQuantity('sl-rice', '1');
    expect(page.canSubmit()).toBe(false);
    page.setReason('   ');
    expect(page.canSubmit()).toBe(false);
    refresh();
    const chip = Array.from(element().querySelectorAll('button.chip')).find((b) => (b.textContent ?? '').includes('Damaged')) as HTMLButtonElement;
    chip.click();
    expect(page.reason()).toBe('Damaged');
    expect(page.canSubmit()).toBe(true);
  });

  it('submits the lines with decimal strings and opens the credit note', () => {
    create();
    page.setQuantity('sl-rice', '1');
    page.setQuantity('sl-soap', '2.5');
    page.setReason('  Damaged  ');
    page.submit();
    expect(returnsApi.create).toHaveBeenCalledTimes(1);
    const [saleId, request, key] = returnsApi.create.mock.calls[0];
    expect(saleId).toBe('s-1');
    expect(request).toEqual({ reason: 'Damaged', lines: [{ sale_line_id: 'sl-rice', quantity: '1.000' }, { sale_line_id: 'sl-soap', quantity: '2.500' }] });
    expect(typeof key).toBe('string');
    expect(navigate).toHaveBeenCalledWith(['/gst/credit-notes', 'cn-1']);
  });

  it('retries a failed return with the same idempotency key and a changed one with a new key', () => {
    returnsApi.create.mockReturnValue(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    create();
    page.setQuantity('sl-rice', '1');
    page.setReason('Damaged');
    page.submit();
    page.submit();
    expect(returnsApi.create.mock.calls[1][2]).toBe(returnsApi.create.mock.calls[0][2]);
    page.setQuantity('sl-rice', '2');
    page.submit();
    expect(returnsApi.create.mock.calls[2][2]).not.toBe(returnsApi.create.mock.calls[0][2]);
    expect(navigate).not.toHaveBeenCalled();
  });

  it('shows server details and a safe-retry message for network failures', () => {
    create();
    page.setQuantity('sl-rice', '1');
    page.setReason('Damaged');
    returnsApi.create.mockReturnValueOnce(throwError(() => new ApiError('VALIDATION_ERROR', 'Invalid', { lines: ['Cannot return 1 of RICE-1: only 0.500 of 2.000 sold can still be returned.'] }, null, 400)));
    page.submit();
    refresh();
    expect(text()).toContain('only 0.500 of 2.000 sold can still be returned');
    returnsApi.create.mockReturnValueOnce(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    page.submit();
    refresh();
    expect(text()).toContain('will not be refunded twice');
  });

  it('does not submit twice while a request is in flight', () => {
    create();
    page.setQuantity('sl-rice', '1');
    page.setReason('Damaged');
    page.submitting.set(true);
    page.submit();
    expect(returnsApi.create).not.toHaveBeenCalled();
  });

  it('explains when everything has already been returned', () => {
    salesApi.get.mockReturnValue(of(sale({ lines: [{ ...riceLine, returned_quantity: '2.000' }] })));
    create();
    expect(text()).toContain('Everything on this invoice has already been returned');
    expect(text()).not.toContain('Issue credit note');
  });

  it('shows not-found and load-failure states', () => {
    salesApi.get.mockReturnValue(throwError(() => new ApiError('NOT_FOUND', 'Sale not found.', {}, null, 404)));
    create();
    expect(text()).toContain('Invoice not found');
    salesApi.get.mockReturnValue(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    create();
    expect(text()).toContain('We could not load this invoice');
  });
});
