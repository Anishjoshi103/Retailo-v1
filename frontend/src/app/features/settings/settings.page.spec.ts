import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { BranchesApi, BranchGst } from './branches.api';
import { SettingsPage } from './settings.page';

const GSTIN = '27AAPFU0939F1ZV';

function branch(overrides: Partial<BranchGst> = {}): BranchGst {
  return { id: 'b-1', name: 'Main Branch', code: 'MAIN', gstin: '', state_code: '', ...overrides };
}

describe('SettingsPage', () => {
  let fixture: ComponentFixture<SettingsPage>;
  let page: SettingsPage;
  let api: { list: ReturnType<typeof vi.fn>; updateGst: ReturnType<typeof vi.fn> };

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();

  function create(): void {
    fixture = TestBed.createComponent(SettingsPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    api = { list: vi.fn().mockReturnValue(of([branch()])), updateGst: vi.fn().mockImplementation((id: string, body: { gstin: string; state_code: string }) => of(branch({ id, ...body }))) };
    TestBed.configureTestingModule({ imports: [SettingsPage], providers: [provideRouter([]), { provide: BranchesApi, useValue: api }] });
  });

  it('links to the staff section', () => {
    create();
    const hrefs = Array.from(element().querySelectorAll('nav.tabs a')).map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/settings', '/settings/staff']);
  });

  it('lists the branches and says which are not ready to bill', () => {
    create();
    expect(text()).toContain('Main Branch');
    expect(text()).toContain('Branch code MAIN');
    expect(text()).toContain('Not ready to bill');
    expect(page.ready(page.branches()[0])).toBe(false);
  });

  it('marks a branch with a state and a valid code as ready to bill', () => {
    api.list.mockReturnValue(of([branch({ state_code: '27' })]));
    create();
    expect(text()).toContain('Ready to bill');
  });

  it('warns that a branch code over five characters cannot issue invoices', () => {
    api.list.mockReturnValue(of([branch({ code: 'NORTHSIDE', state_code: '27' })]));
    create();
    expect(text()).toContain('9 characters; invoices need 5 or fewer');
    expect(text()).toContain('Not ready to bill');
  });

  it('saves a state on its own and shows the branch as ready', () => {
    create();
    const saved = page.branches()[0];
    page.setState(saved, '27');
    expect(page.dirty(saved)).toBe(true);
    page.save(saved);
    refresh();
    expect(api.updateGst).toHaveBeenCalledWith('b-1', { gstin: '', state_code: '27' });
    expect(text()).toContain('Saved');
    expect(text()).toContain('Ready to bill');
    expect(page.dirty(page.branches()[0])).toBe(false);
  });

  it('fills in the state from a valid GSTIN', () => {
    create();
    page.setGstin(page.branches()[0], ` ${GSTIN.toLowerCase()} `);
    expect(page.draft(page.branches()[0])).toEqual({ gstin: GSTIN, stateCode: '27' });
    page.save(page.branches()[0]);
    expect(api.updateGst).toHaveBeenCalledWith('b-1', { gstin: GSTIN, state_code: '27' });
  });

  it('rejects a malformed GSTIN and a GSTIN that does not match the chosen state', () => {
    create();
    const current = page.branches()[0];
    page.setGstin(current, 'NOT-A-GSTIN');
    refresh();
    expect(text()).toContain('15-character format');
    expect(page.canSave(current)).toBe(false);
    page.setGstin(current, GSTIN);
    page.setState(current, '29');
    refresh();
    expect(text()).toContain('does not match the selected state');
    expect(page.canSave(current)).toBe(false);
    page.save(current);
    expect(api.updateGst).not.toHaveBeenCalled();
  });

  it('lets a GSTIN be cleared', () => {
    api.list.mockReturnValue(of([branch({ gstin: GSTIN, state_code: '27' })]));
    create();
    page.setGstin(page.branches()[0], '');
    expect(page.canSave(page.branches()[0])).toBe(true);
    page.save(page.branches()[0]);
    expect(api.updateGst).toHaveBeenCalledWith('b-1', { gstin: '', state_code: '27' });
  });

  it('keeps edits per branch independent', () => {
    api.list.mockReturnValue(of([branch(), branch({ id: 'b-2', name: 'North', code: 'NORTH' })]));
    create();
    page.setState(page.branches()[0], '27');
    expect(page.dirty(page.branches()[0])).toBe(true);
    expect(page.dirty(page.branches()[1])).toBe(false);
  });

  it('shows the server message when saving fails', () => {
    api.updateGst.mockReturnValueOnce(throwError(() => new ApiError('VALIDATION_ERROR', 'Invalid', { gstin: ['The GSTIN\'s first two digits must match the state code.'] }, null, 400)));
    create();
    page.setState(page.branches()[0], '27');
    page.save(page.branches()[0]);
    refresh();
    expect(text()).toContain('first two digits must match');
    api.updateGst.mockReturnValueOnce(throwError(() => new ApiError('FORBIDDEN', 'No', {}, null, 403)));
    page.save(page.branches()[0]);
    refresh();
    expect(text()).toContain('Only the store owner or an administrator');
  });

  it('does not save twice while a save is in flight', () => {
    create();
    page.setState(page.branches()[0], '27');
    page.saves.set({ 'b-1': { kind: 'saving' } });
    expect(page.canSave(page.branches()[0])).toBe(false);
  });

  it('shows a load error with retry and an empty state', () => {
    api.list.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(text()).toContain('We could not load your branches');
    api.list.mockReturnValue(of([]));
    page.load();
    refresh();
    expect(text()).toContain('No branches are available to you');
  });
});
