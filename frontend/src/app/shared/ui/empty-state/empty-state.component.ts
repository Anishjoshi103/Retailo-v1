import { ChangeDetectionStrategy, Component, input } from '@angular/core';
@Component({selector:'rt-empty-state',standalone:true,templateUrl:'./empty-state.component.html',styleUrl:'./empty-state.component.scss',changeDetection:ChangeDetectionStrategy.OnPush})
export class EmptyStateComponent { title=input.required<string>(); description=input(''); }
