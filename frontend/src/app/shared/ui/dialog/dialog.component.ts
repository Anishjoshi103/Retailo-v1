import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
@Component({selector:'rt-dialog',standalone:true,templateUrl:'./dialog.component.html',styleUrl:'./dialog.component.scss',changeDetection:ChangeDetectionStrategy.OnPush})
export class DialogComponent { open=input(false); title=input.required<string>(); close=output<void>(); }
