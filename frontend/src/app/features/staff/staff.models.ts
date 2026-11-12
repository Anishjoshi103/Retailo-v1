/** Shapes of the staff API (`/staff`). */

export type StaffRole = 'owner' | 'admin' | 'manager' | 'cashier' | 'accountant';

export interface StaffMember {
  /** The membership id (used in URLs), not the user id. */
  readonly id: string;
  readonly email: string;
  readonly display_name: string;
  readonly role: StaffRole;
  readonly is_active: boolean;
  /** True until the person has set their password from the invitation email. */
  readonly invited: boolean;
  readonly branch_ids: readonly string[];
  readonly is_self: boolean;
  /** Whether the caller may change or deactivate this member. */
  readonly can_manage: boolean;
  readonly created_at: string;
}

export interface InviteStaffRequest {
  readonly email: string;
  readonly role: Exclude<StaffRole, 'owner'>;
  readonly branch_ids: readonly string[];
  readonly display_name?: string;
}

export interface InvitedStaffMember extends StaffMember {
  /** False when the invitation email could not be sent; the invitation can be resent. */
  readonly invite_sent: boolean;
}

export interface UpdateStaffRequest {
  readonly role?: Exclude<StaffRole, 'owner'>;
  readonly branch_ids?: readonly string[];
  readonly is_active?: boolean;
}
