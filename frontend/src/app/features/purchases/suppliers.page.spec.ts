import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { PurchasesApi } from './purchases.api';
import { Supplier } from './purchases.models';
import { SuppliersPage } from './suppliers.page';

const GSTIN = '27AAPFU0939F1ZV';

function supplier(overrides: Partial<Supplier> = {}): Supplier {
  return { id: 's-1', name: 'Agro Foods', gstin: GSTIN, phone: '98200 00000', email: 'sales@agro.test', address: 'Mumbai', is_active: true, created_at: '2026-11-10T10:00:00Z', updated_at: '2026-11-10T10:00:00Z', ...overrides };
}

describe('SuppliersPage', () => {
  let fixture: ComponentFixture<SuppliersPage>;
  let page: SuppliersPage;
  let api: { suppliers: ReturnType<typeof vi.fn>; createSupplier: ReturnType<typeof vi.fn> };
  let roles: ReturnType<typeof signal<readonly string[]>>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(SuppliersPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    roles = signal<readonly string[]>(['manager']);
    api = {
      suppliers: vi.fn().mockReturnValue(of([supplier(), supplier({ id: 's-2', name: 'Old Traders', gstin: '', is_active: false })])),
      createSupplier: vi.fn().mockImplementation((body: { name: string }) => of(supplier({ id: 's-new', name: body.name }))),
    };
    TestBed.configureTestingModule({
      imports: [SuppliersPage],
      providers: [provideRouter([]), { provide: PurchasesApi, useValue: api }, { provide: SessionContextService, useValue: { roles } }],
    });
  });

  it('lists suppliers with their details and marks inactive ones', () => {
    create();
    expect(api.suppliers).toHaveBeenCalledWith({});
    expect(text()).toContain('Agro Foods');
    expect(text()).toContain(GSTIN);
    expect(text()).toContain('No GSTIN');
    expect(text()).toContain('Inactive');
    const hrefs = Array.from(element().querySelectorAll('nav.tabs a')).map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/purchases', '/purchases/suppliers']);
  });

  it('searches and filters to active suppliers through the API', () => {
    create();
    page.search.set('  agro ');
    api.suppliers.mockClear();
    page.load();
    expect(api.suppliers).toHaveBeenCalledWith({ search: 'agro' });
    page.setFilter('active');
    expect(api.suppliers).toHaveBeenLastCalledWith({ search: 'agro', active: true });
  });

  it('shows empty and error states', () => {
    api.suppliers.mockReturnValue(of([]));
    create();
    expect(text()).toContain('No suppliers found');
    api.suppliers.mockReturnValue(throwError(() => new Error('offline')));
    page.load();
    refresh();
    expect(text()).toContain('We could not load your suppliers');
    api.suppliers.mockReturnValue(of([supplier()]));
    page.load();
    refresh();
    expect(text()).toContain('Agro Foods');
  });

  it('offers adding only to managers, admins and owners', () => {
    create();
    expect(text()).toContain('Add a supplier');
    roles.set(['accountant']);
    refresh();
    expect(page.canCreate()).toBe(false);
    expect(text()).not.toContain('Add a supplier');
  });

  it('needs a name and validates the GSTIN and email before saving', () => {
    create();
    page.openForm();
    expect(page.canSave()).toBe(false);
    page.name.set('New Supplier');
    expect(page.canSave()).toBe(true);
    page.gstin.set('NOT-A-GSTIN');
    refresh();
    expect(page.gstinError()).toContain('15-character');
    expect(text()).toContain('15-character');
    expect(page.canSave()).toBe(false);
    page.gstin.set(' 27aapfu0939f1zv ');
    expect(page.normalizedGstin()).toBe(GSTIN);
    expect(page.canSave()).toBe(true);
    page.email.set('nope');
    expect(page.emailError()).toContain('valid email');
    expect(page.canSave()).toBe(false);
  });

  it('adds a supplier, sending only the fields that were filled, and puts it first in the list', () => {
    create();
    page.openForm();
    page.name.set('  New Supplier ');
    page.gstin.set('27aapfu0939f1zv');
    page.phone.set('');
    page.save();
    refresh();
    expect(api.createSupplier).toHaveBeenCalledWith({ name: 'New Supplier', gstin: GSTIN });
    expect(page.suppliers()[0].name).toBe('New Supplier');
    expect(text()).toContain('New Supplier was added.');
    expect(page.formOpen()).toBe(false);
    expect(page.name()).toBe('');
  });

  it('shows the server\'s message for a duplicate GSTIN next to the field', () => {
    api.createSupplier.mockReturnValueOnce(throwError(() => new ApiError('VALIDATION_ERROR', 'Invalid', { gstin: ['A supplier with this GSTIN already exists in this store.'] }, null, 400)));
    create();
    page.openForm();
    page.name.set('Dup');
    page.gstin.set(GSTIN);
    page.save();
    refresh();
    expect(page.fieldError('gstin')).toContain('already exists');
    expect(text()).toContain('A supplier with this GSTIN already exists');
    expect(page.suppliers()).toHaveLength(2);
    expect(page.formOpen()).toBe(true);
  });

  it('explains permission and connection failures', () => {
    create();
    page.openForm();
    page.name.set('X');
    api.createSupplier.mockReturnValueOnce(throwError(() => new ApiError('FORBIDDEN', 'no', {}, null, 403)));
    page.save();
    refresh();
    expect(text()).toContain('Only a manager, administrator or the owner');
    api.createSupplier.mockReturnValueOnce(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    page.save();
    refresh();
    expect(text()).toContain('could not reach the server');
  });

  it('does not save twice while a save is in flight', () => {
    create();
    page.openForm();
    page.name.set('X');
    page.saving.set(true);
    page.save();
    expect(api.createSupplier).not.toHaveBeenCalled();
  });
});
