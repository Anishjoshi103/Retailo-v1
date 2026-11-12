import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { BranchesApi, BranchGst } from '../settings/branches.api';
import { StaffApi } from './staff.api';
import { InvitedStaffMember, StaffMember } from './staff.models';
import { StaffPage } from './staff.page';

const main: BranchGst = { id: 'b-main', name: 'Main Branch', code: 'MAIN', gstin: '', state_code: '27' };
const north: BranchGst = { id: 'b-north', name: 'North', code: 'NORTH', gstin: '', state_code: '27' };

function member(overrides: Partial<StaffMember> = {}): StaffMember {
  return { id: 'm-1', email: 'asha@example.test', display_name: 'Asha', role: 'cashier', is_active: true, invited: false, branch_ids: ['b-main'], is_self: false, can_manage: true, created_at: '2026-11-10T10:00:00Z', ...overrides };
}

const owner = member({ id: 'm-owner', email: 'owner@example.test', display_name: '', role: 'owner', is_self: true, can_manage: false, branch_ids: ['b-main', 'b-north'] });

describe('StaffPage', () => {
  let fixture: ComponentFixture<StaffPage>;
  let page: StaffPage;
  let staffApi: { list: ReturnType<typeof vi.fn>; invite: ReturnType<typeof vi.fn>; update: ReturnType<typeof vi.fn>; resendInvite: ReturnType<typeof vi.fn> };
  let roles: ReturnType<typeof signal<readonly string[]>>;

  const element = (): HTMLElement => fixture.nativeElement as HTMLElement;
  const text = (): string => element().textContent ?? '';
  const refresh = (): void => fixture.detectChanges();
  const button = (label: string): HTMLButtonElement => {
    const found = Array.from(element().querySelectorAll('button')).find((b) => (b.textContent ?? '').includes(label));
    if (!found) throw new Error(`No button "${label}"`);
    return found;
  };

  function create(): void {
    fixture = TestBed.createComponent(StaffPage);
    page = fixture.componentInstance;
    refresh();
  }

  beforeEach(() => {
    roles = signal<readonly string[]>(['owner']);
    staffApi = {
      list: vi.fn().mockReturnValue(of([owner, member()])),
      invite: vi.fn().mockImplementation((body: { email: string; role: StaffMember['role']; branch_ids: string[] }) =>
        of({ ...member({ id: 'm-new', email: body.email, display_name: '', role: body.role, invited: true, branch_ids: body.branch_ids }), invite_sent: true } satisfies InvitedStaffMember)),
      update: vi.fn().mockImplementation((id: string, body: Partial<StaffMember>) => of({ ...member({ id }), ...body })),
      resendInvite: vi.fn().mockReturnValue(of({ invite_sent: true })),
    };
    TestBed.configureTestingModule({
      imports: [StaffPage],
      providers: [
        provideRouter([]),
        { provide: StaffApi, useValue: staffApi },
        { provide: BranchesApi, useValue: { list: vi.fn().mockReturnValue(of([main, north])) } },
        { provide: SessionContextService, useValue: { roles } },
      ],
    });
  });

  it('lists people with role, branches and status, and offers no actions on the owner row', () => {
    create();
    expect(text()).toContain('People (2)');
    expect(text()).toContain('Asha');
    expect(text()).toContain('asha@example.test');
    expect(text()).toContain('Cashier · Main Branch');
    expect(text()).toContain('Owner · Main Branch, North');
    expect(text()).toContain('(you)');
    const rows = element().querySelectorAll('li.member');
    expect(rows[0].querySelectorAll('button').length).toBe(0);
    expect(rows[1].textContent).toContain('Edit');
  });

  it('shows Invited and Inactive statuses', () => {
    staffApi.list.mockReturnValue(of([owner, member({ invited: true }), member({ id: 'm-2', is_active: false })]));
    create();
    expect(page.status(page.members()[1])).toBe('Invited');
    expect(page.status(page.members()[2])).toBe('Inactive');
    expect(text()).toContain('Resend invitation');
    expect(text()).toContain('Restore access');
  });

  it('offers the administrator role to owners but not to admins', () => {
    create();
    expect(page.roleOptions().map((o) => o.value)).toEqual(['admin', 'manager', 'cashier', 'accountant']);
    roles.set(['admin']);
    expect(page.roleOptions().map((o) => o.value)).toEqual(['manager', 'cashier', 'accountant']);
  });

  it('needs a valid email and at least one branch before inviting', () => {
    create();
    expect(page.canInvite()).toBe(false);
    page.inviteEmail.set('not-an-email');
    refresh();
    expect(text()).toContain('Enter a valid email address.');
    page.inviteEmail.set('new@example.test');
    expect(page.canInvite()).toBe(false);
    page.toggleInviteBranch('b-main');
    expect(page.canInvite()).toBe(true);
    page.toggleInviteBranch('b-main');
    expect(page.canInvite()).toBe(false);
  });

  it('invites a person, adds them to the list and clears the form', () => {
    create();
    page.inviteEmail.set('  new@example.test ');
    page.inviteName.set(' Ravi ');
    page.setInviteRole('manager');
    page.toggleInviteBranch('b-main');
    page.toggleInviteBranch('b-north');
    page.invite();
    refresh();
    expect(staffApi.invite).toHaveBeenCalledWith({ email: 'new@example.test', role: 'manager', branch_ids: ['b-main', 'b-north'], display_name: 'Ravi' });
    expect(page.members().map((m) => m.email)).toContain('new@example.test');
    expect(text()).toContain('Invitation sent to new@example.test');
    expect(page.inviteEmail()).toBe('');
    expect(page.inviteBranchIds()).toEqual([]);
  });

  it('omits an empty name and warns when the invitation email could not be sent', () => {
    staffApi.invite.mockReturnValue(of({ ...member({ id: 'm-new', email: 'new@example.test' }), invite_sent: false }));
    create();
    page.inviteEmail.set('new@example.test');
    page.toggleInviteBranch('b-main');
    page.invite();
    refresh();
    expect(staffApi.invite.mock.calls[0][0]).not.toHaveProperty('display_name');
    expect(text()).toContain('could not be sent');
    expect(text()).toContain('Resend invitation');
  });

  it('explains an email that already has an account and other server errors', () => {
    create();
    page.inviteEmail.set('taken@example.test');
    page.toggleInviteBranch('b-main');
    staffApi.invite.mockReturnValueOnce(throwError(() => new ApiError('CONFLICT', 'x', {}, null, 409)));
    page.invite();
    refresh();
    expect(text()).toContain('already has an account');
    staffApi.invite.mockReturnValueOnce(throwError(() => new ApiError('NETWORK', 'offline', {}, null, 0)));
    page.invite();
    refresh();
    expect(text()).toContain('could not reach the server');
    expect(page.members()).toHaveLength(2);
  });

  it('edits a role and branches, sending only what changed', () => {
    create();
    const target = page.members()[1];
    page.startEdit(target);
    expect(page.canSaveEdit(target)).toBe(false);
    page.setEditRole('manager');
    expect(page.canSaveEdit(target)).toBe(true);
    page.saveEdit(target);
    expect(staffApi.update).toHaveBeenCalledWith('m-1', { role: 'manager' });
    expect(page.editingId()).toBeNull();
    expect(page.members()[1].role).toBe('manager');
    page.startEdit(page.members()[1]);
    page.toggleEditBranch('b-north');
    page.saveEdit(page.members()[1]);
    expect(staffApi.update).toHaveBeenLastCalledWith('m-1', { branch_ids: ['b-main', 'b-north'] });
  });

  it('will not save an edit that leaves no branch', () => {
    create();
    const target = page.members()[1];
    page.startEdit(target);
    page.toggleEditBranch('b-main');
    refresh();
    expect(text()).toContain('Choose at least one branch.');
    expect(page.canSaveEdit(target)).toBe(false);
  });

  it('asks for confirmation before removing access, then restores it on request', () => {
    create();
    const target = page.members()[1];
    page.askDeactivate(target);
    refresh();
    expect(text()).toContain('signed out of the app straight away');
    expect(staffApi.update).not.toHaveBeenCalled();
    page.cancelDeactivate();
    expect(page.confirmingId()).toBeNull();
    page.askDeactivate(target);
    page.deactivate(target);
    refresh();
    expect(staffApi.update).toHaveBeenCalledWith('m-1', { is_active: false });
    expect(page.members()[1].is_active).toBe(false);
    expect(text()).toContain('Access removed.');
    expect(text()).toContain('Restore access');
    page.reactivate(page.members()[1]);
    expect(staffApi.update).toHaveBeenLastCalledWith('m-1', { is_active: true });
    expect(page.members()[1].is_active).toBe(true);
  });

  it('resends an invitation and reports the outcome', () => {
    staffApi.list.mockReturnValue(of([owner, member({ invited: true })]));
    create();
    page.resend(page.members()[1]);
    refresh();
    expect(staffApi.resendInvite).toHaveBeenCalledWith('m-1');
    expect(text()).toContain('Invitation sent again to asha@example.test');
    staffApi.resendInvite.mockReturnValueOnce(of({ invite_sent: false }));
    page.resend(page.members()[1]);
    refresh();
    expect(text()).toContain('could not be sent. Try again');
  });

  it('shows the server message when an update is refused', () => {
    staffApi.update.mockReturnValueOnce(throwError(() => new ApiError('FORBIDDEN', 'You do not have permission to change this member.', {}, null, 403)));
    create();
    page.askDeactivate(page.members()[1]);
    page.deactivate(page.members()[1]);
    refresh();
    expect(text()).toContain('You do not have permission to change this member.');
    expect(page.members()[1].is_active).toBe(true);
  });

  it('does not start a second action while one is in flight', () => {
    create();
    page.busyId.set('m-1');
    page.deactivate(page.members()[1]);
    page.resend(page.members()[1]);
    expect(staffApi.update).not.toHaveBeenCalled();
    expect(staffApi.resendInvite).not.toHaveBeenCalled();
  });

  it('shows a load error with retry, and a message for people who are not allowed', () => {
    staffApi.list.mockReturnValue(throwError(() => new Error('offline')));
    create();
    expect(text()).toContain('We could not load your staff');
    staffApi.list.mockReturnValue(throwError(() => new ApiError('FORBIDDEN', 'no', {}, null, 403)));
    page.load();
    refresh();
    expect(text()).toContain('Only the store owner or an administrator');
    staffApi.list.mockReturnValue(of([owner]));
    page.load();
    refresh();
    expect(text()).toContain('People (1)');
  });

  it('links back to the branches section', () => {
    create();
    const hrefs = Array.from(element().querySelectorAll('nav.tabs a')).map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/settings', '/settings/staff']);
    expect(button('Send invitation')).toBeTruthy();
  });
});
