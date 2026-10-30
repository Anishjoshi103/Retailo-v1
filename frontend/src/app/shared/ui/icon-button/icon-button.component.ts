import { ChangeDetectionStrategy, Component, input } from '@angular/core';
@Component({ selector:'rt-icon-button', standalone:true, templateUrl:'./icon-button.component.html', styleUrl:'./icon-button.component.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class IconButtonComponent { label=input.required<string>(); disabled=input(false); }
