import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { SessionContextService } from '../../core/auth/session-context.service';
import { ReportsPage } from './reports.page';
import { ReportsApi } from './reports.api';
import { ReportTotals, SalesSummary } from './reports.models';

function totals(overrides: Partial<ReportTotals> = {}): ReportTotals {
  return { count: 2, taxable_total: '264.73', cgst_total: '17.63', sgst_total: '17.63', igst_total: '0.00', total_tax: '35.26', round_off: '0.01', grand_total: '300.00', ...overrides };
}

function summary(overrides: Partial<SalesSummary> = {}): SalesSummary {
  return {
    date_from: '2026-11-16', date_to: '2026-11-16', branch_id: 'b-1', branch_count: 1,
    sales: totals(),
    returns: totals({ count: 1, taxable_total: '84.75', cgst_total: '7.63', sgst_total: '7.63', total_tax: '15.26', round_off: '-0.01', grand_total: '100.00' }),
    net: { taxable_total: '179.98', total_tax: '20.00', grand_total: '200.00' },
    payments: [{ method: 'cash', amount: '200.00', count: 1 }, { method: 'upi', amount: '100.00', count: 1 }],
    by_day: [{ date: '2026-11-16', sales_count: 2, sales_total: '300.00', returns_count: 1, returns_total: '100.00', net_total: '200.00' }],
    ...overrides,
  };
}

describe('ReportsPage', () => {
  let fixture: ComponentFixture<ReportsPage>;
  let page: ReportsPage;
  let api: { salesSummary: ReturnType<typeof vi.fn> };
  let branchId: ReturnType<typeof signal<string | null>>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(ReportsPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 10, 16, 12, 0));
    api = { salesSummary: vi.fn().mockReturnValue(of(summary())) };
    branchId = signal<string | null>('b-1');
    TestBed.configureTestingModule({
      imports: [ReportsPage],
      providers: [provideRouter([]), { provide: ReportsApi, useValue: api }, { provide: SessionContextService, useValue: { selectedBranchId: branchId } }],
    });
  });

  afterEach(() => vi.useRealTimers());

  it('links to the GST register', () => {
    create();
    const hrefs = Array.from(element().querySelectorAll('nav.tabs a')).map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/reports', '/reports/gst']);
  });

  it('loads today for the selected branch and leaves "today" to the server', () => {
    create();
    expect(api.salesSummary).toHaveBeenCalledWith({ branchId: 'b-1' });
    expect(text()).toContain('2026-11-16');
    expect(text()).toContain('this branch');
  });

  it('shows the headline, sales, returns, tax and how customers paid', () => {
    create();
    const content = text();
    expect(content).toContain('Net sales');
    expect(content).toContain('₹200.00');
    expect(content).toContain('₹300.00 sold less ₹100.00 returned');
    expect(content).toContain('Credit notes');
    expect(content).toContain('Cash refunded');
    expect(content).toContain('₹264.73');
    expect(content).toContain('₹17.63');
    expect(content).toContain('₹35.26');
    expect(content).toContain('₹20.00 on ₹179.98');
    expect(content).toContain('Cash');
    expect(content).toContain('UPI');
    expect(content).toContain('₹100.00');
  });

  it('works out cash in hand as cash sales less cash refunds, even when it is negative', () => {
    create();
    expect(page.cashInHandPaise()).toBe(10000);
    expect(text()).toContain('₹100.00');
    api.salesSummary.mockReturnValue(of(summary({ payments: [{ method: 'upi', amount: '300.00', count: 2 }] })));
    page.load();
    refresh();
    expect(page.cashInHandPaise()).toBe(-10000);
    expect(text()).toContain('-₹100.00');
  });

  it('reloads for each preset using exact calendar days', () => {
    create();
    page.choosePreset('yesterday');
    expect(api.salesSummary).toHaveBeenLastCalledWith({ dateFrom: '2026-11-15', dateTo: '2026-11-15', branchId: 'b-1' });
    page.choosePreset('week');
    expect(api.salesSummary).toHaveBeenLastCalledWith({ dateFrom: '2026-11-10', dateTo: '2026-11-16', branchId: 'b-1' });
    page.choosePreset('month');
    expect(api.salesSummary).toHaveBeenLastCalledWith({ dateFrom: '2026-11-01', dateTo: '2026-11-16', branchId: 'b-1' });
    page.choosePreset('today');
    expect(api.salesSummary).toHaveBeenLastCalledWith({ branchId: 'b-1' });
  });

  it('can report on every branch the person may see', () => {
    api.salesSummary.mockReturnValue(of(summary({ branch_id: null, branch_count: 3 })));
    create();
    page.setScope('all');
    refresh();
    expect(api.salesSummary).toHaveBeenLastCalledWith({});
    expect(text()).toContain('3 branch(es)');
    page.setScope('branch');
    expect(api.salesSummary).toHaveBeenLastCalledWith({ branchId: 'b-1' });
  });

  it('needs both dates for a custom range and rejects a reversed or over-long one', () => {
    create();
    api.salesSummary.mockClear();
    page.chooseCustom();
    refresh();
    expect(text()).toContain('Choose both a start and an end date.');
    expect(api.salesSummary).not.toHaveBeenCalled();
    page.customFrom.set('2026-11-10');
    page.customTo.set('2026-11-01');
    refresh();
    expect(text()).toContain('The start date is after the end date.');
    page.load();
    expect(api.salesSummary).not.toHaveBeenCalled();
    page.customFrom.set('2025-01-01');
    page.customTo.set('2026-01-02');
    expect(page.customProblem()).toContain('at most 366 days');
    page.customTo.set('2026-01-01');
    expect(page.customProblem()).toBe('');
  });

  it('runs a valid custom range', () => {
    create();
    page.chooseCustom();
    page.customFrom.set('2026-10-01');
    page.customTo.set('2026-10-31');
    page.load();
    expect(api.salesSummary).toHaveBeenLastCalledWith({ dateFrom: '2026-10-01', dateTo: '2026-10-31', branchId: 'b-1' });
  });

  it('reloads when the branch changes and does not ask for a branch report without one', () => {
    create();
    api.salesSummary.mockClear();
    branchId.set('b-2');
    refresh();
    expect(api.salesSummary).toHaveBeenCalledWith({ branchId: 'b-2' });
    api.salesSummary.mockClear();
    branchId.set(null);
    refresh();
    expect(api.salesSummary).not.toHaveBeenCalled();
    expect(page.summary()).toBeNull();
    page.setScope('all');
    expect(api.salesSummary).toHaveBeenCalledWith({});
  });

  it('shows an empty state when nothing happened', () => {
    api.salesSummary.mockReturnValue(of(summary({ sales: totals({ count: 0, grand_total: '0.00' }), returns: totals({ count: 0, grand_total: '0.00' }), payments: [], by_day: [] })));
    create();
    expect(text()).toContain('No sales in this period');
    expect(text()).not.toContain('Net sales');
  });

  it('shows the daily table only when the range covers more than one active day', () => {
    create();
    expect(text()).not.toContain('By day');
    api.salesSummary.mockReturnValue(of(summary({ by_day: [
      { date: '2026-11-15', sales_count: 1, sales_total: '100.00', returns_count: 0, returns_total: '0.00', net_total: '100.00' },
      { date: '2026-11-16', sales_count: 1, sales_total: '200.00', returns_count: 1, returns_total: '100.00', net_total: '100.00' },
    ] })));
    page.choosePreset('week');
    refresh();
    expect(text()).toContain('By day');
    expect(text()).toContain('2026-11-15');
  });

  it('shows an error with retry', () => {
    api.salesSummary.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(text()).toContain('We could not load the report');
    api.salesSummary.mockReturnValue(of(summary()));
    page.load();
    refresh();
    expect(page.errorMessage()).toBe('');
    expect(text()).toContain('Net sales');
  });

  it('ignores a response that a newer request has superseded', () => {
    create();
    let firstEmit: (value: SalesSummary) => void = () => undefined;
    const slow = { subscribe: (observer: { next: (value: SalesSummary) => void }) => { firstEmit = observer.next; return { unsubscribe: () => undefined }; } };
    api.salesSummary.mockReturnValueOnce({ pipe: () => slow });
    page.choosePreset('week');
    api.salesSummary.mockReturnValueOnce(of(summary({ net: { taxable_total: '1.00', total_tax: '0.00', grand_total: '1.00' } })));
    page.choosePreset('month');
    firstEmit(summary({ net: { taxable_total: '9.00', total_tax: '0.00', grand_total: '9.00' } }));
    expect(page.summary()?.net.grand_total).toBe('1.00');
  });
});
