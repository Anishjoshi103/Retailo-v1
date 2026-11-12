import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';

export interface BranchGst {
  readonly id: string;
  readonly name: string;
  readonly code: string;
  readonly gstin: string;
  readonly state_code: string;
}

export interface UpdateBranchGstRequest {
  readonly gstin: string;
  readonly state_code: string;
}

@Injectable({ providedIn: 'root' })
export class BranchesApi {
  private readonly api = inject(ApiClient);

  list(): Observable<readonly BranchGst[]> {
    return this.api.get<readonly BranchGst[]>('branches');
  }

  /** Owner/admin only. Sets the branch's GSTIN and GST state code (either may be blank). */
  updateGst(branchId: string, request: UpdateBranchGstRequest): Observable<BranchGst> {
    return this.api.patch<BranchGst, UpdateBranchGstRequest>(`branches/${encodeURIComponent(branchId)}`, request);
  }
}
