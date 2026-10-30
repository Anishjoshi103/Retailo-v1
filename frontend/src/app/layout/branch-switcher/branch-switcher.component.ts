import { ChangeDetectionStrategy, Component, EventEmitter, inject, Output } from '@angular/core';
import { RouteRoleContext } from '../../core/auth/role-branch.guard';
import { TenantContextService } from '../../core/tenant-context/tenant-context.service';

interface BranchOption { readonly id: string; readonly name: string; }

@Component({
  selector: 'retailo-branch-switcher',
  standalone: true,
  templateUrl: './branch-switcher.component.html',
  styleUrl: './branch-switcher.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class BranchSwitcherComponent {
  private readonly tenantContext = inject(TenantContextService);
  private readonly routeContext = inject(RouteRoleContext);
  @Output() readonly branchChanged = new EventEmitter<string>();
  readonly branches: readonly BranchOption[] = [
    { id: 'demo-main', name: 'Main Branch' },
    { id: 'demo-west', name: 'West Branch' }
  ];
  selectedBranchId = this.branches[0].id;

  constructor() {
    this.tenantContext.setBranch(this.selectedBranchId);
    this.routeContext.branchId.set(this.selectedBranchId);
  }

  onBranchSelect(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) return;
    const branchId = target.value;
    if (!this.branches.some((branch) => branch.id === branchId)) return;
    this.selectedBranchId = branchId;
    this.tenantContext.setBranch(branchId);
    this.routeContext.branchId.set(branchId);
    this.branchChanged.emit(branchId);
  }
}