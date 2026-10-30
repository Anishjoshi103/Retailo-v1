import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
export interface SelectOption { label:string; value:string; }
@Component({selector:'rt-select',standalone:true,templateUrl:'./select.component.html',styleUrl:'./select.component.scss',changeDetection:ChangeDetectionStrategy.OnPush})
export class SelectComponent { label=input.required<string>(); options=input.required<readonly SelectOption[]>(); value=input(''); valueChange=output<string>(); }
