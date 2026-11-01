import { ChangeDetectionStrategy, Component, EventEmitter, Output, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { SessionContextService } from '../../core/auth/session-context.service';
import { SessionService } from '../../core/auth/session.service';
import { BranchSwitcherComponent } from '../branch-switcher/branch-switcher.component';
import { finalize } from 'rxjs';
@Component({ selector:'retailo-topbar', standalone:true, imports:[RouterLink, BranchSwitcherComponent], templateUrl:'./topbar.component.html', styleUrl:'./topbar.component.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class TopbarComponent {
  @Output() readonly menuToggle = new EventEmitter<void>();
  private readonly session = inject(SessionService);
  private readonly context = inject(SessionContextService);
  private readonly router = inject(Router);
  signOut(): void {
    this.session.logout().pipe(finalize(() => {
      this.context.clear();
      void this.router.navigate(['/auth/login']);
    })).subscribe();
  }
}
