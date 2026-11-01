import { ChangeDetectionStrategy, Component, EventEmitter, inject, Output } from '@angular/core';
import { SessionContextService } from '../../core/auth/session-context.service';

@Component({
  selector: 'retailo-branch-switcher',
  standalone: true,
  templateUrl: './branch-switcher.component.html',
  styleUrl: './branch-switcher.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class BranchSwitcherComponent {
  private readonly context = inject(SessionContextService);
  @Output() readonly branchChanged = new EventEmitter<string>();
  get branches() { return this.context.branches(); }
  get selectedBranchId(): string { return this.context.selectedBranchId() ?? ''; }

  onBranchSelect(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) return;
    const id = target.value;
    if (!this.context.selectBranch(id)) return;
    this.branchChanged.emit(id);
  }
}