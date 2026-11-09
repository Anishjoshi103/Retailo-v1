import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { SessionContextService } from '../../core/auth/session-context.service';
import { SalesApi } from '../pos/sales.api';
import { SaleSummary } from '../pos/sales.models';
import { InvoicesPage } from './invoices.page';

function summary(index: number, overrides: Partial<SaleSummary> = {}): SaleSummary {
  return {
    id: `s-${index}`, invoice_number: `INV-MAIN-${String(index).padStart(6, '0')}`, invoice_date: '2026-11-09', branch_id: 'b-1',
    customer_name: '', taxable_total: '84.74', total_tax: '15.26', round_off: '0.00', grand_total: '100.00',
    created_at: '2026-11-09T10:00:00Z', ...overrides,
  };
}

describe('InvoicesPage', () => {
  let fixture: ComponentFixture<InvoicesPage>;
  let page: InvoicesPage;
  let salesApi: { list: ReturnType<typeof vi.fn> };
  let branchId: ReturnType<typeof signal<string | null>>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(InvoicesPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    salesApi = { list: vi.fn().mockReturnValue(of([summary(2), summary(1)])) };
    branchId = signal<string | null>('b-1');
    TestBed.configureTestingModule({
      imports: [InvoicesPage],
      providers: [
        provideRouter([]),
        { provide: SalesApi, useValue: salesApi },
        { provide: SessionContextService, useValue: { selectedBranchId: branchId } },
      ],
    });
  });

  it('loads the newest invoices for the selected branch and links each to its detail page', () => {
    create();
    expect(salesApi.list).toHaveBeenCalledWith({ branchId: 'b-1', invoiceNumber: undefined, dateFrom: undefined, dateTo: undefined, limit: 50, offset: 0 });
    expect(text()).toContain('INV-MAIN-000002');
    expect(text()).toContain('₹100.00');
    expect(text()).toContain('Walk-in');
    const links = Array.from(element().querySelectorAll('a.invoice-link')).map((a) => a.getAttribute('href'));
    expect(links).toEqual(['/gst/s-2', '/gst/s-1']);
  });

  it('shows an empty state when there are no invoices', () => {
    salesApi.list.mockReturnValue(of([]));
    create();
    expect(text()).toContain('No invoices found');
  });

  it('searches with the entered filters from the first page', () => {
    create();
    salesApi.list.mockClear();
    page.invoiceNumber.set('  INV-MAIN-000001 ');
    page.dateFrom.set('2026-11-01');
    page.dateTo.set('2026-11-09');
    page.reload();
    expect(salesApi.list).toHaveBeenCalledWith({ branchId: 'b-1', invoiceNumber: 'INV-MAIN-000001', dateFrom: '2026-11-01', dateTo: '2026-11-09', limit: 50, offset: 0 });
  });

  it('does not search when the date range is reversed', () => {
    create();
    salesApi.list.mockClear();
    page.dateFrom.set('2026-11-09');
    page.dateTo.set('2026-11-01');
    page.reload();
    refresh();
    expect(salesApi.list).not.toHaveBeenCalled();
    expect(text()).toContain('From date is after the To date');
  });

  it('clears filters and reloads', () => {
    create();
    page.invoiceNumber.set('X');
    page.clearFilters();
    expect(page.invoiceNumber()).toBe('');
    expect(salesApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ invoiceNumber: undefined, offset: 0 }));
  });

  it('offers Load more only after a full page and appends the next page', () => {
    const fullPage = Array.from({ length: 50 }, (_, i) => summary(100 - i));
    salesApi.list.mockReturnValue(of(fullPage));
    create();
    expect(page.hasMore()).toBe(true);
    expect(text()).toContain('Load more');
    salesApi.list.mockReturnValue(of([summary(1)]));
    page.loadMore();
    refresh();
    expect(salesApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50 }));
    expect(page.sales()).toHaveLength(51);
    expect(page.hasMore()).toBe(false);
    expect(text()).not.toContain('Load more');
  });

  it('shows an error with a retry that reloads', () => {
    salesApi.list.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(text()).toContain('We could not load invoices');
    expect(text()).not.toContain('No invoices found');
    salesApi.list.mockReturnValue(of([summary(1)]));
    page.reload();
    refresh();
    expect(page.errorMessage()).toBe('');
    expect(text()).toContain('INV-MAIN-000001');
  });

  it('reloads when the selected branch changes', () => {
    create();
    salesApi.list.mockClear();
    branchId.set('b-2');
    refresh();
    expect(salesApi.list).toHaveBeenCalledWith(expect.objectContaining({ branchId: 'b-2', offset: 0 }));
  });

  it('does not request anything without a selected branch', () => {
    branchId.set(null);
    create();
    expect(salesApi.list).not.toHaveBeenCalled();
  });

  it('ignores a response that a newer search has superseded', () => {
    create();
    let firstEmit: (rows: readonly SaleSummary[]) => void = () => undefined;
    const slow = { subscribe: (observer: { next: (rows: readonly SaleSummary[]) => void }) => { firstEmit = observer.next; return { unsubscribe: () => undefined }; } };
    salesApi.list.mockReturnValueOnce({ pipe: () => slow });
    page.reload();
    salesApi.list.mockReturnValueOnce(of([summary(9)]));
    page.reload();
    firstEmit([summary(1)]);
    expect(page.sales().map((s) => s.id)).toEqual(['s-9']);
  });
});
