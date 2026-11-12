import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin, Observable } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { BranchesApi, BranchGst } from '../settings/branches.api';
import { StaffApi } from './staff.api';
import { StaffMember, StaffRole } from './staff.models';

type AssignableRole = Exclude<StaffRole, 'owner'>;

interface RoleOption {
  readonly value: AssignableRole;
  readonly label: string;
  readonly hint: string;
}

const ALL_ROLES: readonly RoleOption[] = [
  { value: 'admin', label: 'Administrator', hint: 'Manages staff and settings; cannot change the owner.' },
  { value: 'manager', label: 'Manager', hint: 'Bills, takes returns and can sell below available stock.' },
  { value: 'cashier', label: 'Cashier', hint: 'Bills and takes returns.' },
  { value: 'accountant', label: 'Accountant', hint: 'Read-only access to invoices and records.' },
];

const ROLE_LABELS: Readonly<Record<StaffRole, string>> = { owner: 'Owner', admin: 'Administrator', manager: 'Manager', cashier: 'Cashier', accountant: 'Accountant' };

type Message = { readonly kind: 'ok' | 'warn' | 'error'; readonly text: string } | null;

@Component({
  selector: 'app-staff-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './staff.page.html',
  styleUrl: './staff.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StaffPage {
  private readonly staffApi = inject(StaffApi);
  private readonly branchesApi = inject(BranchesApi);
  private readonly session = inject(SessionContextService);

  readonly members = signal<readonly StaffMember[]>([]);
  readonly branches = signal<readonly BranchGst[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal('');

  /** Admins may not hand out the administrator role; owners may. */
  readonly roleOptions = computed<readonly RoleOption[]>(() =>
    this.session.roles().includes('owner') ? ALL_ROLES : ALL_ROLES.filter((option) => option.value !== 'admin'));

  // Invite form
  readonly inviteEmail = signal('');
  readonly inviteName = signal('');
  readonly inviteRole = signal<AssignableRole>('cashier');
  readonly inviteBranchIds = signal<readonly string[]>([]);
  readonly inviting = signal(false);
  readonly inviteMessage = signal<Message>(null);

  // Per-member editing
  readonly editingId = signal<string | null>(null);
  readonly editRole = signal<AssignableRole>('cashier');
  readonly editBranchIds = signal<readonly string[]>([]);
  readonly confirmingId = signal<string | null>(null);
  readonly busyId = signal<string | null>(null);
  readonly rowMessage = signal<{ readonly id: string; readonly message: NonNullable<Message> } | null>(null);

  readonly roleLabels = ROLE_LABELS;

  readonly emailValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.inviteEmail().trim()));
  readonly canInvite = computed(() => !this.inviting() && this.emailValid() && this.inviteBranchIds().length > 0);

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set('');
    forkJoin({ members: this.staffApi.list(), branches: this.branchesApi.list() }).subscribe({
      next: ({ members, branches }) => { this.members.set(members); this.branches.set(branches); this.loading.set(false); },
      error: (error: unknown) => {
        this.loadError.set(error instanceof ApiError && error.status === 403
          ? 'Only the store owner or an administrator can manage staff.'
          : 'We could not load your staff. Check your connection and try again.');
        this.loading.set(false);
      },
    });
  }

  branchNames(member: StaffMember): string {
    const names = this.branches().filter((branch) => member.branch_ids.includes(branch.id)).map((branch) => branch.name);
    return names.length > 0 ? names.join(', ') : 'No branches';
  }

  status(member: StaffMember): 'Inactive' | 'Invited' | 'Active' {
    if (!member.is_active) return 'Inactive';
    return member.invited ? 'Invited' : 'Active';
  }

  // ---- invite
  toggleInviteBranch(branchId: string): void {
    this.inviteBranchIds.update((ids) => this.toggled(ids, branchId));
  }

  invite(): void {
    if (!this.canInvite()) return;
    const email = this.inviteEmail().trim();
    const name = this.inviteName().trim();
    this.inviting.set(true);
    this.inviteMessage.set(null);
    this.staffApi.invite({ email, role: this.inviteRole(), branch_ids: this.inviteBranchIds(), ...(name ? { display_name: name } : {}) }).subscribe({
      next: (created) => {
        this.inviting.set(false);
        this.inviteEmail.set('');
        this.inviteName.set('');
        this.inviteBranchIds.set([]);
        this.members.update((all) => [...all, created]);
        this.inviteMessage.set(created.invite_sent
          ? { kind: 'ok', text: `Invitation sent to ${created.email}. They can set a password from the link in the email.` }
          : { kind: 'warn', text: `${created.email} was added, but the invitation email could not be sent. Use Resend invitation to try again.` });
      },
      error: (error: unknown) => { this.inviting.set(false); this.inviteMessage.set({ kind: 'error', text: this.describe(error) }); },
    });
  }

  // ---- edit
  startEdit(member: StaffMember): void {
    this.confirmingId.set(null);
    this.editingId.set(member.id);
    this.editRole.set(member.role === 'owner' ? 'cashier' : member.role);
    this.editBranchIds.set(member.branch_ids);
    this.rowMessage.set(null);
  }

  cancelEdit(): void {
    this.editingId.set(null);
  }

  toggleEditBranch(branchId: string): void {
    this.editBranchIds.update((ids) => this.toggled(ids, branchId));
  }

  canSaveEdit(member: StaffMember): boolean {
    return this.busyId() === null && this.editBranchIds().length > 0
      && (this.editRole() !== member.role || !this.sameSet(this.editBranchIds(), member.branch_ids));
  }

  saveEdit(member: StaffMember): void {
    if (!this.canSaveEdit(member)) return;
    const request = {
      ...(this.editRole() !== member.role ? { role: this.editRole() } : {}),
      ...(!this.sameSet(this.editBranchIds(), member.branch_ids) ? { branch_ids: this.editBranchIds() } : {}),
    };
    this.run(member, () => this.staffApi.update(member.id, request), 'Changes saved.', () => this.editingId.set(null));
  }

  // ---- deactivate / reactivate / resend
  askDeactivate(member: StaffMember): void {
    this.editingId.set(null);
    this.confirmingId.set(member.id);
    this.rowMessage.set(null);
  }

  cancelDeactivate(): void {
    this.confirmingId.set(null);
  }

  deactivate(member: StaffMember): void {
    this.run(member, () => this.staffApi.update(member.id, { is_active: false }), 'Access removed.', () => this.confirmingId.set(null));
  }

  reactivate(member: StaffMember): void {
    this.run(member, () => this.staffApi.update(member.id, { is_active: true }), 'Access restored.');
  }

  resend(member: StaffMember): void {
    if (this.busyId() !== null) return;
    this.busyId.set(member.id);
    this.rowMessage.set(null);
    this.staffApi.resendInvite(member.id).subscribe({
      next: (result) => {
        this.busyId.set(null);
        this.rowMessage.set({ id: member.id, message: result.invite_sent
          ? { kind: 'ok', text: `Invitation sent again to ${member.email}.` }
          : { kind: 'warn', text: 'The invitation email could not be sent. Try again in a moment.' } });
      },
      error: (error: unknown) => { this.busyId.set(null); this.rowMessage.set({ id: member.id, message: { kind: 'error', text: this.describe(error) } }); },
    });
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  setInviteRole(value: string): void {
    const option = this.roleOptions().find((item) => item.value === value);
    if (option) this.inviteRole.set(option.value);
  }

  setEditRole(value: string): void {
    const option = this.roleOptions().find((item) => item.value === value);
    if (option) this.editRole.set(option.value);
  }

  roleHint(role: AssignableRole): string {
    return ALL_ROLES.find((option) => option.value === role)?.hint ?? '';
  }

  /** Runs one member action at a time; the request is only built once nothing else is in flight. */
  private run(member: StaffMember, request: () => Observable<StaffMember>, success: string, done?: () => void): void {
    if (this.busyId() !== null) return;
    this.busyId.set(member.id);
    this.rowMessage.set(null);
    request().subscribe({
      next: (updated) => {
        this.busyId.set(null);
        this.members.update((all) => all.map((item) => (item.id === updated.id ? updated : item)));
        this.rowMessage.set({ id: member.id, message: { kind: 'ok', text: success } });
        done?.();
      },
      error: (error: unknown) => { this.busyId.set(null); this.rowMessage.set({ id: member.id, message: { kind: 'error', text: this.describe(error) } }); },
    });
  }

  private toggled(ids: readonly string[], id: string): readonly string[] {
    return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
  }

  private sameSet(a: readonly string[], b: readonly string[]): boolean {
    return a.length === b.length && a.every((id) => b.includes(id));
  }

  private describe(error: unknown): string {
    if (error instanceof ApiError) {
      if (error.status === 0) return 'We could not reach the server. Try again.';
      if (error.status === 409) return 'This email address already has an account.';
      if (error.status === 403) return error.message || 'You do not have permission to do that.';
      const details = Object.values(error.fieldErrors).flat();
      return details.length > 0 ? details.join(' ') : error.message;
    }
    return 'Something went wrong. Please try again.';
  }
}
