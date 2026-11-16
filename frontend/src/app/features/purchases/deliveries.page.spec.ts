import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { SessionContextService } from '../../core/auth/session-context.service';
import { DeliveriesPage } from './deliveries.page';
import { PurchasesApi } from './purchases.api';
import { ReceiptSummary } from './purchases.models';

function delivery(index: number, overrides: Partial<ReceiptSummary> = {}): ReceiptSummary {
  return { id: `r-${index}`, branch_id: 'b-1', supplier_id: null, supplier_name: `Supplier ${index}`, supplier_invoice_number: `AF-${index}`, received_at: '2026-11-10T09:30:00Z', line_count: 2, total_cost: '425.00', ...overrides };
}

describe('DeliveriesPage', () => {
  let fixture: ComponentFixture<DeliveriesPage>;
  let page: DeliveriesPage;
  let api: { receipts: ReturnType<typeof vi.fn> };
  let branchId: ReturnType<typeof signal<string | null>>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(DeliveriesPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    api = { receipts: vi.fn().mockReturnValue(of([delivery(2), delivery(1, { supplier_invoice_number: '' })])) };
    branchId = signal<string | null>('b-1');
    TestBed.configureTestingModule({
      imports: [DeliveriesPage],
      providers: [provideRouter([]), { provide: PurchasesApi, useValue: api }, { provide: SessionContextService, useValue: { selectedBranchId: branchId } }],
    });
  });

  it('loads this branch\'s deliveries and links each to its detail page', () => {
    create();
    expect(api.receipts).toHaveBeenCalledWith({ branchId: 'b-1', invoiceNumber: undefined, dateFrom: undefined, dateTo: undefined, limit: 50, offset: 0 });
    expect(text()).toContain('Supplier 2');
    expect(text()).toContain('2026-11-10');
    expect(text()).toContain('₹425.00');
    expect(text()).toContain('—');
    const links = Array.from(element().querySelectorAll('a.row-link')).map((a) => a.getAttribute('href'));
    expect(links).toEqual(['/purchases/history/r-2', '/purchases/history/r-1']);
    const tabs = Array.from(element().querySelectorAll('nav.tabs a')).map((a) => a.getAttribute('href'));
    expect(tabs).toEqual(['/purchases', '/purchases/history', '/purchases/suppliers']);
  });

  it('shows an empty state', () => {
    api.receipts.mockReturnValue(of([]));
    create();
    expect(text()).toContain('No deliveries found');
  });

  it('searches with the entered filters and rejects a reversed date range', () => {
    create();
    api.receipts.mockClear();
    page.invoiceNumber.set(' AF-10 ');
    page.dateFrom.set('2026-11-01');
    page.dateTo.set('2026-11-10');
    page.reload();
    expect(api.receipts).toHaveBeenCalledWith({ branchId: 'b-1', invoiceNumber: 'AF-10', dateFrom: '2026-11-01', dateTo: '2026-11-10', limit: 50, offset: 0 });
    api.receipts.mockClear();
    page.dateFrom.set('2026-11-10');
    page.dateTo.set('2026-11-01');
    page.reload();
    refresh();
    expect(api.receipts).not.toHaveBeenCalled();
    expect(text()).toContain('From date is after the To date');
  });

  it('clears filters and reloads', () => {
    create();
    page.invoiceNumber.set('X');
    page.clearFilters();
    expect(page.invoiceNumber()).toBe('');
    expect(api.receipts).toHaveBeenLastCalledWith(expect.objectContaining({ invoiceNumber: undefined, offset: 0 }));
  });

  it('offers Load more after a full page and appends the next page', () => {
    api.receipts.mockReturnValue(of(Array.from({ length: 50 }, (_, i) => delivery(100 - i))));
    create();
    expect(page.hasMore()).toBe(true);
    api.receipts.mockReturnValue(of([delivery(1)]));
    page.loadMore();
    expect(api.receipts).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50 }));
    expect(page.deliveries()).toHaveLength(51);
    expect(page.hasMore()).toBe(false);
  });

  it('shows an error with retry', () => {
    api.receipts.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(text()).toContain('We could not load deliveries');
    api.receipts.mockReturnValue(of([delivery(1)]));
    page.reload();
    refresh();
    expect(page.errorMessage()).toBe('');
    expect(text()).toContain('Supplier 1');
  });

  it('reloads when the branch changes and requests nothing without one', () => {
    create();
    api.receipts.mockClear();
    branchId.set('b-2');
    refresh();
    expect(api.receipts).toHaveBeenCalledWith(expect.objectContaining({ branchId: 'b-2' }));
    api.receipts.mockClear();
    branchId.set(null);
    refresh();
    expect(api.receipts).not.toHaveBeenCalled();
  });

  it('ignores a response that a newer search has superseded', () => {
    create();
    let firstEmit: (rows: readonly ReceiptSummary[]) => void = () => undefined;
    const slow = { subscribe: (observer: { next: (rows: readonly ReceiptSummary[]) => void }) => { firstEmit = observer.next; return { unsubscribe: () => undefined }; } };
    api.receipts.mockReturnValueOnce({ pipe: () => slow });
    page.reload();
    api.receipts.mockReturnValueOnce(of([delivery(9)]));
    page.reload();
    firstEmit([delivery(1)]);
    expect(page.deliveries().map((d) => d.id)).toEqual(['r-9']);
  });
});
