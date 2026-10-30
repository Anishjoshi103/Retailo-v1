import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
@Component({selector:'rt-toast',standalone:true,templateUrl:'./toast.component.html',styleUrl:'./toast.component.scss',changeDetection:ChangeDetectionStrategy.OnPush})
export class ToastComponent { message=input.required<string>(); tone=input<'success'|'warning'|'danger'>('success'); dismiss=output<void>(); }
