import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { SessionContextService } from '../../core/auth/session-context.service';
import { CreditNotesPage } from './credit-notes.page';
import { ReturnsApi } from './returns.api';
import { CreditNoteSummary } from './returns.models';

function summary(index: number, overrides: Partial<CreditNoteSummary> = {}): CreditNoteSummary {
  return {
    id: `cn-${index}`, credit_note_number: `CN-MAIN-${String(index).padStart(6, '0')}`, credit_note_date: '2026-11-10',
    sale_id: `s-${index}`, invoice_number: `INV-MAIN-${String(index).padStart(6, '0')}`, branch_id: 'b-1',
    reason: 'Damaged', customer_name: '', grand_total: '100.00', created_at: '2026-11-10T10:00:00Z', ...overrides,
  };
}

describe('CreditNotesPage', () => {
  let fixture: ComponentFixture<CreditNotesPage>;
  let page: CreditNotesPage;
  let returnsApi: { list: ReturnType<typeof vi.fn> };
  let branchId: ReturnType<typeof signal<string | null>>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(CreditNotesPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    returnsApi = { list: vi.fn().mockReturnValue(of([summary(2), summary(1)])) };
    branchId = signal<string | null>('b-1');
    TestBed.configureTestingModule({
      imports: [CreditNotesPage],
      providers: [
        provideRouter([]),
        { provide: ReturnsApi, useValue: returnsApi },
        { provide: SessionContextService, useValue: { selectedBranchId: branchId } },
      ],
    });
  });

  it('loads the newest credit notes for the selected branch and links to each note and its invoice', () => {
    create();
    expect(returnsApi.list).toHaveBeenCalledWith({ branchId: 'b-1', creditNoteNumber: undefined, dateFrom: undefined, dateTo: undefined, limit: 50, offset: 0 });
    expect(text()).toContain('CN-MAIN-000002');
    expect(text()).toContain('Damaged');
    expect(text()).toContain('₹100.00');
    const links = Array.from(element().querySelectorAll('a.note-link')).map((a) => a.getAttribute('href'));
    expect(links).toEqual(['/gst/credit-notes/cn-2', '/gst/s-2', '/gst/credit-notes/cn-1', '/gst/s-1']);
  });

  it('shows an empty state', () => {
    returnsApi.list.mockReturnValue(of([]));
    create();
    expect(text()).toContain('No credit notes found');
  });

  it('searches with the entered filters and rejects a reversed date range', () => {
    create();
    returnsApi.list.mockClear();
    page.creditNoteNumber.set(' CN-MAIN-000001 ');
    page.dateFrom.set('2026-11-01');
    page.dateTo.set('2026-11-10');
    page.reload();
    expect(returnsApi.list).toHaveBeenCalledWith({ branchId: 'b-1', creditNoteNumber: 'CN-MAIN-000001', dateFrom: '2026-11-01', dateTo: '2026-11-10', limit: 50, offset: 0 });
    returnsApi.list.mockClear();
    page.dateFrom.set('2026-11-10');
    page.dateTo.set('2026-11-01');
    page.reload();
    refresh();
    expect(returnsApi.list).not.toHaveBeenCalled();
    expect(text()).toContain('From date is after the To date');
  });

  it('offers Load more after a full page and appends the next page', () => {
    returnsApi.list.mockReturnValue(of(Array.from({ length: 50 }, (_, i) => summary(100 - i))));
    create();
    expect(page.hasMore()).toBe(true);
    returnsApi.list.mockReturnValue(of([summary(1)]));
    page.loadMore();
    expect(returnsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50 }));
    expect(page.notes()).toHaveLength(51);
    expect(page.hasMore()).toBe(false);
  });

  it('shows an error with a retry', () => {
    returnsApi.list.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(text()).toContain('We could not load credit notes');
    returnsApi.list.mockReturnValue(of([summary(1)]));
    page.reload();
    refresh();
    expect(page.errorMessage()).toBe('');
    expect(text()).toContain('CN-MAIN-000001');
  });

  it('reloads when the selected branch changes and requests nothing without one', () => {
    create();
    returnsApi.list.mockClear();
    branchId.set('b-2');
    refresh();
    expect(returnsApi.list).toHaveBeenCalledWith(expect.objectContaining({ branchId: 'b-2' }));
    returnsApi.list.mockClear();
    branchId.set(null);
    refresh();
    expect(returnsApi.list).not.toHaveBeenCalled();
  });
});
