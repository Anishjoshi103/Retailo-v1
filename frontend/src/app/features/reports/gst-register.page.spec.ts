import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { FileSaver } from '../../core/files/file-saver.service';
import { SessionContextService } from '../../core/auth/session-context.service';
import { GstRegisterPage } from './gst-register.page';
import { ReportsApi } from './reports.api';
import { GstRegister } from './reports.models';

function register(overrides: Partial<GstRegister> = {}): GstRegister {
  return {
    date_from: '2026-10-01', date_to: '2026-10-31', branch_id: 'b-1', branch_count: 1,
    rates: [
      { place_of_supply: '27', gst_rate: '5.00', taxable_value: '95.23', igst: '0.00', cgst: '2.38', sgst: '2.38', cess: '0.00', sales_taxable_value: '95.23', returns_taxable_value: '0.00' },
      { place_of_supply: '27', gst_rate: '18.00', taxable_value: '169.49', igst: '0.00', cgst: '15.25', sgst: '15.25', cess: '0.00', sales_taxable_value: '254.24', returns_taxable_value: '84.75' },
    ],
    hsn: [
      { hsn_code: '', description: '=Mystery', uqc: 'NOS', quantity: '2.000', total_value: '20.00', taxable_value: '20.00', igst: '0.00', cgst: '0.00', sgst: '0.00', cess: '0.00', gst_rate: '0.00' },
      { hsn_code: '1006', description: 'Rice', uqc: 'KGS', quantity: '2.000', total_value: '199.99', taxable_value: '169.49', igst: '0.00', cgst: '15.25', sgst: '15.25', cess: '0.00', gst_rate: '18.00' },
    ],
    documents: [
      { document_type: 'Invoices for outward supply', series: 'MAIN', from: 'INV-MAIN-000001', to: 'INV-MAIN-000002', total: 2, cancelled: 0 },
      { document_type: 'Credit notes', series: 'MAIN', from: 'CN-MAIN-000001', to: 'CN-MAIN-000001', total: 1, cancelled: 0 },
    ],
    totals: { taxable_value: '264.72', cgst: '17.63', sgst: '17.63', igst: '0.00', total_tax: '35.26' },
    missing_hsn_lines: 1,
    ...overrides,
  };
}

describe('GstRegisterPage', () => {
  let fixture: ComponentFixture<GstRegisterPage>;
  let page: GstRegisterPage;
  let api: { gstRegister: ReturnType<typeof vi.fn>; gstRegisterCsv: ReturnType<typeof vi.fn> };
  let branchId: ReturnType<typeof signal<string | null>>;
  let saved: ReturnType<typeof vi.fn>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(GstRegisterPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 10, 16, 12, 0));
    api = { gstRegister: vi.fn().mockReturnValue(of(register())), gstRegisterCsv: vi.fn().mockReturnValue(of(new Blob(['a,b']))) };
    branchId = signal<string | null>('b-1');
    saved = vi.fn();
    TestBed.configureTestingModule({
      imports: [GstRegisterPage],
      providers: [provideRouter([]), { provide: FileSaver, useValue: { save: saved } }, { provide: ReportsApi, useValue: api }, { provide: SessionContextService, useValue: { selectedBranchId: branchId } }],
    });
  });

  afterEach(() => vi.useRealTimers());

  it('starts with last month for this branch, the period returns are normally filed for', () => {
    create();
    expect(api.gstRegister).toHaveBeenCalledWith({ dateFrom: '2026-10-01', dateTo: '2026-10-31', branchId: 'b-1' });
    expect(text()).toContain('2026-10-01 to 2026-10-31');
    const hrefs = Array.from(element().querySelectorAll('nav.tabs a')).map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/reports', '/reports/gst']);
  });

  it('shows totals and the three tables', () => {
    create();
    const content = text();
    expect(content).toContain('₹264.72');
    expect(content).toContain('₹35.26');
    expect(content).toContain('Sales by tax rate');
    expect(content).toContain('18.00%');
    expect(content).toContain('₹15.25');
    expect(content).toContain('HSN summary');
    expect(content).toContain('1006');
    expect(content).toContain('KGS');
    expect(content).toContain('Documents issued');
    expect(content).toContain('INV-MAIN-000002');
    expect(content).toContain('CN-MAIN-000001');
    expect(content).toContain('Have an accountant review');
  });

  it('warns about items with no HSN code and shows a dash for them', () => {
    create();
    expect(text()).toContain('1 sold item line(s) have no HSN code');
    const firstHsn = element().querySelectorAll('table')[1].querySelector('tbody tr td')?.textContent;
    expect(firstHsn).toBe('—');
    api.gstRegister.mockReturnValue(of(register({ missing_hsn_lines: 0 })));
    page.load();
    refresh();
    expect(text()).not.toContain('have no HSN code');
  });

  it('switches period and scope', () => {
    create();
    page.choose('month');
    expect(api.gstRegister).toHaveBeenLastCalledWith({ dateFrom: '2026-11-01', dateTo: '2026-11-16', branchId: 'b-1' });
    page.setScope('all');
    expect(api.gstRegister).toHaveBeenLastCalledWith({ dateFrom: '2026-11-01', dateTo: '2026-11-16' });
  });

  it('needs a valid custom range', () => {
    create();
    api.gstRegister.mockClear();
    page.choose('custom');
    refresh();
    expect(text()).toContain('Choose both a start and an end date.');
    page.customFrom.set('2026-10-31');
    page.customTo.set('2026-10-01');
    expect(page.customProblem()).toContain('after the end date');
    page.load();
    expect(api.gstRegister).not.toHaveBeenCalled();
    page.customFrom.set('2025-01-01');
    page.customTo.set('2026-01-02');
    expect(page.customProblem()).toContain('at most 366 days');
    page.customFrom.set('2026-09-01');
    page.customTo.set('2026-09-30');
    page.load();
    expect(api.gstRegister).toHaveBeenLastCalledWith({ dateFrom: '2026-09-01', dateTo: '2026-09-30', branchId: 'b-1' });
  });

  it('downloads each table for exactly the period and branch shown, under a clear file name', () => {
    create();
    page.download('hsn');
    expect(api.gstRegisterCsv).toHaveBeenCalledWith('hsn', { dateFrom: '2026-10-01', dateTo: '2026-10-31', branchId: 'b-1' });
    expect(saved).toHaveBeenCalledWith(expect.any(Blob), 'gst-hsn-2026-10-01-to-2026-10-31.csv');
    page.setScope('all');
    api.gstRegister.mockReturnValue(of(register({ branch_id: null, branch_count: 2 })));
    page.load();
    page.download('rates');
    expect(api.gstRegisterCsv).toHaveBeenLastCalledWith('rates', { dateFrom: '2026-10-01', dateTo: '2026-10-31' });
  });

  it('downloads the period that is on screen even if the controls changed since', () => {
    create();
    page.customFrom.set('2026-01-01');
    page.range.set('custom');
    page.download('documents');
    expect(api.gstRegisterCsv).toHaveBeenCalledWith('documents', { dateFrom: '2026-10-01', dateTo: '2026-10-31', branchId: 'b-1' });
  });

  it('shows an error if a download fails, does not save anything, and allows one download at a time', () => {
    create();
    api.gstRegisterCsv.mockReturnValueOnce(throwError(() => new Error('offline')));
    page.download('rates');
    refresh();
    expect(text()).toContain('We could not download that file');
    expect(saved).not.toHaveBeenCalled();
    expect(page.downloading()).toBeNull();
    api.gstRegisterCsv.mockClear();
    page.downloading.set('rates');
    page.download('hsn');
    expect(api.gstRegisterCsv).not.toHaveBeenCalled();
  });

  it('shows an empty state when there is nothing in the period', () => {
    api.gstRegister.mockReturnValue(of(register({ rates: [], hsn: [], documents: [], missing_hsn_lines: 0 })));
    create();
    expect(text()).toContain('Nothing to report');
    expect(text()).not.toContain('Download CSV');
  });

  it('shows an error with retry, and reloads when the branch changes', () => {
    api.gstRegister.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(text()).toContain('We could not load the GST register');
    api.gstRegister.mockReturnValue(of(register()));
    page.load();
    refresh();
    expect(page.errorMessage()).toBe('');
    api.gstRegister.mockClear();
    branchId.set('b-2');
    refresh();
    expect(api.gstRegister).toHaveBeenCalledWith(expect.objectContaining({ branchId: 'b-2' }));
  });

  it('does not ask for a branch register without a branch, but can for all branches', () => {
    create();
    api.gstRegister.mockClear();
    branchId.set(null);
    refresh();
    expect(api.gstRegister).not.toHaveBeenCalled();
    expect(page.register()).toBeNull();
    page.setScope('all');
    expect(api.gstRegister).toHaveBeenCalledTimes(1);
  });
});
