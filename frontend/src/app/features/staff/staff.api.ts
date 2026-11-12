import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { InvitedStaffMember, InviteStaffRequest, StaffMember, UpdateStaffRequest } from './staff.models';

@Injectable({ providedIn: 'root' })
export class StaffApi {
  private readonly api = inject(ApiClient);

  list(): Observable<readonly StaffMember[]> {
    return this.api.get<readonly StaffMember[]>('staff');
  }

  invite(request: InviteStaffRequest): Observable<InvitedStaffMember> {
    return this.api.post<InvitedStaffMember, InviteStaffRequest>('staff', request);
  }

  update(id: string, request: UpdateStaffRequest): Observable<StaffMember> {
    return this.api.patch<StaffMember, UpdateStaffRequest>(`staff/${encodeURIComponent(id)}`, request);
  }

  resendInvite(id: string): Observable<{ readonly invite_sent: boolean }> {
    return this.api.post<{ readonly invite_sent: boolean }, Record<string, never>>(`staff/${encodeURIComponent(id)}/resend-invite`, {});
  }
}
