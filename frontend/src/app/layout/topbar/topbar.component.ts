import { ChangeDetectionStrategy, Component, EventEmitter, Output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BranchSwitcherComponent } from '../branch-switcher/branch-switcher.component';
@Component({ selector:'retailo-topbar', standalone:true, imports:[RouterLink, BranchSwitcherComponent], templateUrl:'./topbar.component.html', styleUrl:'./topbar.component.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class TopbarComponent { @Output() readonly menuToggle = new EventEmitter<void>(); }