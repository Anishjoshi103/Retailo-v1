import { ChangeDetectionStrategy, Component, input } from '@angular/core';
@Component({ selector:'rt-button', standalone:true, templateUrl:'./button.component.html', styleUrl:'./button.component.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class ButtonComponent { label=input.required<string>(); variant=input<'primary'|'secondary'|'danger'>('primary'); type=input<'button'|'submit'|'reset'>('button'); disabled=input(false); }
