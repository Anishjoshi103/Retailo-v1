import { ChangeDetectionStrategy, Component, input } from '@angular/core';
@Component({ selector:'rt-badge', standalone:true, templateUrl:'./badge.component.html', styleUrl:'./badge.component.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class BadgeComponent { tone=input<'neutral'|'success'|'warning'|'danger'>('neutral'); }
