import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { InventoryApi } from './inventory.api';
import { ProductSummary, StockBalance } from './inventory.models';
import { InventoryPage } from './inventory.page';

function balance(product: string, name: string, quantity: string): StockBalance {
  return { id: `bal-${product}`, branch: 'b-1', product, product_sku: product.toUpperCase(), product_name: name, quantity_on_hand: quantity, updated_at: '2026-11-10T10:00:00Z' };
}

const rice = balance('rice', 'Rice', '10.000');
const soap = balance('soap', 'Soap', '0.000');
const oil = balance('oil', 'Oil', '-2.000');
const newProduct: ProductSummary = { id: 'tea', sku: 'TEA', barcode: null, name: 'Tea', unit: 'each', is_active: true };

describe('InventoryPage', () => {
  let fixture: ComponentFixture<InventoryPage>;
  let page: InventoryPage;
  let api: { balances: ReturnType<typeof vi.fn>; searchProducts: ReturnType<typeof vi.fn>; adjust: ReturnType<typeof vi.fn> };
  let roles: ReturnType<typeof signal<readonly string[]>>;
  let branchId: ReturnType<typeof signal<string | null>>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(InventoryPage);
    page = fixture.componentInstance;
    refresh();
  }

  function startCount(row: string, counted: string, reason = 'Stock take'): void {
    page.adjust(page.rows().find((r) => r.balance.product === row) as never);
    page.countedText.set(counted);
    page.reason.set(reason);
  }

  beforeEach(() => {
    roles = signal<readonly string[]>(['manager']);
    branchId = signal<string | null>('b-1');
    api = {
      balances: vi.fn().mockReturnValue(of([rice, soap, oil])),
      searchProducts: vi.fn().mockReturnValue(of([newProduct])),
      adjust: vi.fn().mockImplementation((request: { quantity_delta: string }) => of({ movement_id: 'mv-1', quantity_on_hand: request.quantity_delta, replayed: false })),
    };
    TestBed.configureTestingModule({
      imports: [InventoryPage],
      providers: [{ provide: InventoryApi, useValue: api }, { provide: SessionContextService, useValue: { roles, selectedBranchId: branchId } }],
    });
  });

  it('loads this branch\'s stock sorted by name and flags out-of-stock and below-zero products', () => {
    create();
    expect(api.balances).toHaveBeenCalledWith('b-1', 50, 0, '', false);
    expect(page.rows().map((r) => r.balance.product_name)).toEqual(['Oil', 'Rice', 'Soap']);
    expect(text()).toContain('10.000');
    expect(text()).toContain('-2.000');
    expect(text()).toContain('Below zero');
    expect(text()).toContain('Out of stock');
    expect(page.attentionCount()).toBe(2);
    expect(text()).toContain('1 product(s) are below zero');
  });

  it('searches by name or SKU and can show only products that need attention', () => {
    create();
    page.search.set('ric');
    expect(page.visibleRows().map((r) => r.balance.product)).toEqual(['rice']);
    page.search.set('SOAP');
    expect(page.visibleRows().map((r) => r.balance.product)).toEqual(['soap']);
    page.search.set('');
    page.filter.set('attention');
    expect(page.visibleRows().map((r) => r.balance.product)).toEqual(['oil', 'soap']);
    page.search.set('zzz');
    refresh();
    expect(text()).toContain('Nothing matches');
  });

  it('shows a first-time empty state', () => {
    api.balances.mockReturnValue(of([]));
    create();
    expect(text()).toContain('No stock recorded yet');
  });

  it('reloads when the branch changes and requests nothing without one', () => {
    create();
    api.balances.mockClear();
    branchId.set('b-2');
    refresh();
    expect(api.balances).toHaveBeenCalledWith('b-2', 50, 0, '', false);
    api.balances.mockClear();
    branchId.set(null);
    refresh();
    expect(api.balances).not.toHaveBeenCalled();
    expect(page.balances()).toEqual([]);
  });

  it('shows a load error with retry', () => {
    api.balances.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(text()).toContain('We could not load your stock');
    api.balances.mockReturnValue(of([rice]));
    page.load();
    refresh();
    expect(text()).toContain('Rice');
  });

  it('offers adjusting only to managers, admins and owners', () => {
    create();
    expect(text()).toContain('Adjust');
    expect(text()).toContain('Add stock for another product');
    roles.set(['cashier']);
    refresh();
    expect(text()).not.toContain('Add stock for another product');
    expect(Array.from(element().querySelectorAll('button')).some((button) => button.textContent?.trim() === 'Adjust')).toBe(false);
    roles.set(['accountant']);
    refresh();
    expect(page.canAdjust()).toBe(false);
    roles.set(['owner']);
    expect(page.canAdjust()).toBe(true);
  });

  it('turns a counted quantity into the exact change and previews it', () => {
    create();
    startCount('rice', '7');
    refresh();
    expect(page.delta()).toBe(-3000);
    expect(page.newOnHandMilli()).toBe(7000);
    expect(text()).toContain('-3.000');
    page.submit();
    expect(api.adjust).toHaveBeenCalledTimes(1);
    const [request] = api.adjust.mock.calls[0];
    expect(request).toEqual({ branch_id: 'b-1', product_id: 'rice', quantity_delta: '-3.000', note: 'Stock take' });
  });

  it('counts correctly from below zero and from decimals without drift', () => {
    create();
    startCount('oil', '0');
    expect(page.delta()).toBe(2000);
    page.adjust(page.rows().find((r) => r.balance.product === 'rice') as never);
    page.countedText.set('10.001');
    expect(page.delta()).toBe(1);
    page.countedText.set('0.1');
    expect(page.delta()).toBe(-9900);
  });

  it('adds or removes a signed quantity', () => {
    create();
    page.adjust(page.rows().find((r) => r.balance.product === 'rice') as never);
    page.setMode('change');
    page.reason.set('Damaged');
    page.changeText.set('-2.5');
    expect(page.delta()).toBe(-2500);
    page.submit();
    expect(api.adjust.mock.calls[0][0].quantity_delta).toBe('-2.500');
    page.adjust(page.rows().find((r) => r.balance.product === 'rice') as never);
    page.setMode('change');
    page.reason.set('Found stock');
    page.changeText.set('+5');
    page.submit();
    expect(api.adjust.mock.calls[1][0].quantity_delta).toBe('5.000');
  });

  it('blocks an invalid number, no change and a missing reason', () => {
    create();
    startCount('rice', 'abc');
    refresh();
    expect(page.inputError()).toContain('Enter the counted quantity');
    expect(page.canSubmit()).toBe(false);
    page.countedText.set('10');
    refresh();
    expect(text()).toContain('No change');
    expect(page.canSubmit()).toBe(false);
    page.countedText.set('4');
    page.reason.set('   ');
    expect(page.canSubmit()).toBe(false);
    page.reason.set('Stock take');
    expect(page.canSubmit()).toBe(true);
    page.setMode('change');
    page.changeText.set('1.2345');
    expect(page.inputError()).toContain('Enter a change');
  });

  it('updates the list and confirms the new quantity after saving', () => {
    create();
    startCount('rice', '7');
    api.adjust.mockReturnValueOnce(of({ movement_id: 'mv-1', quantity_on_hand: '7.000', replayed: false }));
    page.submit();
    refresh();
    expect(page.rows().find((r) => r.balance.product === 'rice')?.onHandMilli).toBe(7000);
    expect(page.target()).toBeNull();
    expect(text()).toContain('Rice: stock is now 7.000.');
  });

  it('adds stock for a product that has no stock record yet', () => {
    create();
    page.productSearch.set('tea');
    page.searchProducts();
    expect(api.searchProducts).toHaveBeenCalledWith('tea');
    expect(page.productResults()).toEqual([newProduct]);
    page.adjustProduct(newProduct);
    expect(page.target()?.onHandMilli).toBe(0);
    expect(page.productResults()).toEqual([]);
    page.countedText.set('12');
    page.reason.set('Stock take');
    api.adjust.mockReturnValueOnce(of({ movement_id: 'mv-2', quantity_on_hand: '12.000', replayed: false }));
    page.submit();
    expect(api.adjust.mock.calls[0][0]).toEqual({ branch_id: 'b-1', product_id: 'tea', quantity_delta: '12.000', note: 'Stock take' });
    expect(page.rows().map((r) => r.balance.product)).toContain('tea');
  });

  it('starts from the existing quantity when the chosen product already has stock', () => {
    create();
    page.adjustProduct({ ...newProduct, id: 'rice', sku: 'RICE', name: 'Rice' });
    expect(page.target()?.onHandMilli).toBe(10000);
  });

  it('retries a failed adjustment with the same key and a changed one with a new key', () => {
    create();
    api.adjust.mockReturnValue(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    startCount('rice', '7');
    page.submit();
    page.submit();
    expect(api.adjust.mock.calls[1][1]).toBe(api.adjust.mock.calls[0][1]);
    page.countedText.set('6');
    page.submit();
    expect(api.adjust.mock.calls[2][1]).not.toBe(api.adjust.mock.calls[0][1]);
  });

  it('explains failures', () => {
    create();
    startCount('rice', '7');
    api.adjust.mockReturnValueOnce(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    page.submit();
    refresh();
    expect(text()).toContain('will not be applied twice');
    api.adjust.mockReturnValueOnce(throwError(() => new ApiError('FORBIDDEN', 'no', {}, null, 403)));
    page.submit();
    refresh();
    expect(text()).toContain('Only a manager, administrator or the owner');
    api.adjust.mockReturnValueOnce(throwError(() => new ApiError('VALIDATION_ERROR', 'Invalid', { non_field_errors: ['Select an active branch and product in your store.'] }, null, 400)));
    page.submit();
    refresh();
    expect(text()).toContain('Select an active branch and product');
  });

  it('cancels an adjustment and ignores a second submit while one is in flight', () => {
    create();
    startCount('rice', '7');
    page.submitting.set(true);
    page.submit();
    expect(api.adjust).not.toHaveBeenCalled();
    page.submitting.set(false);
    page.cancelAdjust();
    expect(page.target()).toBeNull();
  });
});
