import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { InventoryApi } from '../inventory/inventory.api';
import { ProductSummary } from '../inventory/inventory.models';
import { PurchasesApi } from './purchases.api';
import { PurchaseReceipt, Supplier } from './purchases.models';
import { ReceiveGoodsPage } from './receive-goods.page';

const rice: ProductSummary = { id: 'p-rice', sku: 'RICE-1', barcode: '8901', name: 'Rice', unit: 'kg', is_active: true };
const soap: ProductSummary = { id: 'p-soap', sku: 'SOAP-1', barcode: null, name: 'Soap', unit: 'each', is_active: true };
const agro: Supplier = { id: 's-1', name: 'Agro Foods', gstin: '', phone: '', email: '', address: '', is_active: true, created_at: '', updated_at: '' };

function receipt(overrides: Partial<PurchaseReceipt> = {}): PurchaseReceipt {
  return { id: 'r-1', branch_id: 'b-1', supplier_id: 's-1', supplier_name: 'Agro Foods', supplier_invoice_number: 'AF-99', received_at: '2026-11-10T10:00:00Z', replayed: false, lines: [{ product_id: 'p-rice', quantity: '10.000', unit_cost: '42.50' }], ...overrides };
}

describe('ReceiveGoodsPage', () => {
  let fixture: ComponentFixture<ReceiveGoodsPage>;
  let page: ReceiveGoodsPage;
  let purchasesApi: { suppliers: ReturnType<typeof vi.fn>; receiveGoods: ReturnType<typeof vi.fn> };
  let inventoryApi: { searchProducts: ReturnType<typeof vi.fn> };

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(ReceiveGoodsPage);
    page = fixture.componentInstance;
    refresh();
  }

  function fillOneLine(): void {
    page.addProduct(rice);
    page.setQuantity('p-rice', '10');
    page.setCost('p-rice', '42.50');
    page.chooseSupplier('s-1');
  }

  beforeEach(() => {
    purchasesApi = { suppliers: vi.fn().mockReturnValue(of([agro])), receiveGoods: vi.fn().mockReturnValue(of(receipt())) };
    inventoryApi = { searchProducts: vi.fn().mockReturnValue(of([rice, soap])) };
    TestBed.configureTestingModule({
      imports: [ReceiveGoodsPage],
      providers: [
        provideRouter([]),
        { provide: PurchasesApi, useValue: purchasesApi },
        { provide: InventoryApi, useValue: inventoryApi },
        { provide: SessionContextService, useValue: { selectedBranchId: signal('b-1') } },
      ],
    });
  });

  it('loads the active saved suppliers', () => {
    create();
    expect(purchasesApi.suppliers).toHaveBeenCalledWith({ active: true });
    expect(text()).toContain('Agro Foods');
  });

  it('still works with a typed supplier name when saved suppliers cannot be loaded', () => {
    purchasesApi.suppliers.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(page.suppliersFailed()).toBe(true);
    expect(text()).toContain('you can still type a name');
    page.supplierName.set('Walk-in Trader');
    expect(page.supplierValid()).toBe(true);
  });

  it('searches, lists matches and adds a product to the delivery', () => {
    create();
    page.search.set('o');
    page.searchProducts();
    refresh();
    expect(inventoryApi.searchProducts).toHaveBeenCalledWith('o');
    expect(text()).toContain('Soap');
    page.addProduct(soap);
    expect(page.lines().map((l) => l.product.id)).toEqual(['p-soap']);
    expect(page.results()).toEqual([]);
  });

  it('adds an exact barcode or SKU match straight to the delivery, and merges repeats', () => {
    inventoryApi.searchProducts.mockReturnValue(of([rice]));
    create();
    page.search.set('8901');
    page.searchProducts();
    expect(page.lines().map((l) => l.product.id)).toEqual(['p-rice']);
    page.addProduct(rice);
    expect(page.lines()).toHaveLength(1);
    expect(page.lines()[0].quantityText).toBe('2.000');
  });

  it('works out each line and the total cost exactly', () => {
    create();
    fillOneLine();
    page.addProduct(soap);
    page.setQuantity('p-soap', '3');
    page.setCost('p-soap', '33.33');
    refresh();
    expect(page.pricedLines().map((p) => p.grossPaise)).toEqual([42500, 9999]);
    expect(page.totalPaise()).toBe(52499);
    expect(text()).toContain('₹524.99');
  });

  it('allows a zero cost but flags a missing or invalid quantity and cost', () => {
    create();
    page.addProduct(rice);
    page.chooseSupplier('s-1');
    page.setQuantity('p-rice', '2');
    page.setCost('p-rice', '0');
    expect(page.linesValid()).toBe(true);
    page.setCost('p-rice', '');
    refresh();
    expect(page.linesValid()).toBe(false);
    expect(text()).toContain('Enter a quantity above zero');
    page.setCost('p-rice', '5');
    page.setQuantity('p-rice', '0');
    expect(page.canSubmit()).toBe(false);
  });

  it('needs a supplier, either saved or typed', () => {
    create();
    page.addProduct(rice);
    page.setCost('p-rice', '10');
    expect(page.canSubmit()).toBe(false);
    page.supplierName.set('   ');
    expect(page.canSubmit()).toBe(false);
    page.supplierName.set('Walk-in Trader');
    expect(page.canSubmit()).toBe(true);
    page.chooseSupplier('s-1');
    expect(page.supplierName()).toBe('');
    expect(page.canSubmit()).toBe(true);
  });

  it('receives the goods using the saved supplier and decimal strings, then shows a summary', () => {
    create();
    fillOneLine();
    page.invoiceNumber.set('  AF-99 ');
    page.submit();
    refresh();
    const [request, key] = purchasesApi.receiveGoods.mock.calls[0];
    expect(request).toEqual({ branch_id: 'b-1', supplier_id: 's-1', supplier_invoice_number: 'AF-99', lines: [{ product_id: 'p-rice', quantity: '10.000', unit_cost: '42.50' }] });
    expect(typeof key).toBe('string');
    expect(text()).toContain('Goods received');
    expect(text()).toContain('Agro Foods');
    expect(text()).toContain('₹425.00');
    expect(element().querySelector('a.link[href="/inventory"]')).not.toBeNull();
  });

  it('sends a typed supplier name when no saved supplier is chosen', () => {
    create();
    page.addProduct(rice);
    page.setQuantity('p-rice', '1');
    page.setCost('p-rice', '10');
    page.supplierName.set(' Walk-in Trader ');
    page.submit();
    expect(purchasesApi.receiveGoods.mock.calls[0][0]).toEqual({ branch_id: 'b-1', supplier_name: 'Walk-in Trader', lines: [{ product_id: 'p-rice', quantity: '1.000', unit_cost: '10.00' }] });
  });

  it('retries a failed delivery with the same key and a changed one with a new key', () => {
    create();
    purchasesApi.receiveGoods.mockReturnValue(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    fillOneLine();
    page.submit();
    page.submit();
    expect(purchasesApi.receiveGoods.mock.calls[1][1]).toBe(purchasesApi.receiveGoods.mock.calls[0][1]);
    page.setQuantity('p-rice', '11');
    page.submit();
    expect(purchasesApi.receiveGoods.mock.calls[2][1]).not.toBe(purchasesApi.receiveGoods.mock.calls[0][1]);
    expect(page.completed()).toBeNull();
  });

  it('explains failures and does not submit twice', () => {
    create();
    fillOneLine();
    purchasesApi.receiveGoods.mockReturnValueOnce(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    page.submit();
    refresh();
    expect(text()).toContain('will not be added twice');
    purchasesApi.receiveGoods.mockReturnValueOnce(throwError(() => new ApiError('FORBIDDEN', 'no', {}, null, 403)));
    page.submit();
    refresh();
    expect(text()).toContain('Only a manager, administrator or the owner');
    purchasesApi.receiveGoods.mockReturnValueOnce(throwError(() => new ApiError('VALIDATION_ERROR', 'Invalid', { lines: ['Every product must be active and belong to your store.'] }, null, 400)));
    page.submit();
    refresh();
    expect(text()).toContain('Every product must be active');
    purchasesApi.receiveGoods.mockClear();
    page.submitting.set(true);
    page.submit();
    expect(purchasesApi.receiveGoods).not.toHaveBeenCalled();
  });

  it('starts a fresh delivery from the summary', () => {
    create();
    fillOneLine();
    page.submit();
    refresh();
    Array.from(element().querySelectorAll('button')).find((b) => (b.textContent ?? '').includes('Receive more goods'))?.click();
    refresh();
    expect(page.completed()).toBeNull();
    expect(page.lines()).toEqual([]);
    expect(page.supplierId()).toBe('');
    expect(text()).toContain('No items yet');
  });

  it('removes a line', () => {
    create();
    fillOneLine();
    page.removeLine('p-rice');
    expect(page.lines()).toEqual([]);
  });
});
