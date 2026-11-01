import { ChangeDetectionStrategy, Component, EventEmitter, inject, Output } from '@angular/core';
import { SessionContextService } from '../../core/auth/session-context.service';
import { TenantContextService } from '../../core/tenant-context/tenant-context.service';
import { RouteRoleContext } from '../../core/auth/role-branch.guard';

@Component({
  selector: 'retailo-branch-switcher',
  standalone: true,
  templateUrl: './branch-switcher.component.html',
  styleUrl: './branch-switcher.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class BranchSwitcherComponent {
  private readonly context = inject(SessionContextService);
  private readonly tenantContext = inject(TenantContextService);
  private readonly routeContext = inject(RouteRoleContext);
  @Output() readonly branchChanged = new EventEmitter<string>();
  get branches() { return this.context.branches(); }
  get selectedBranchId(): string { return this.context.selectedBranchId() ?? ''; }

  constructor() {
    if (this.context.user()) this.context.loadBranches().subscribe((items) => this.propagate(this.context.selectedBranchId() ?? items[0]?.id ?? ''));
  }
  onBranchSelect(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) return;
    const id = target.value;
    if (!this.context.selectBranch(id)) return;
    this.propagate(id);
    this.branchChanged.emit(id);
  }
  private propagate(id: string): void {
    if (!id) return;
    this.tenantContext.setBranch(id);
    this.routeContext.branchId.set(id);
  }
}