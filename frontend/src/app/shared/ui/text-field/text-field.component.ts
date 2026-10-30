import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
@Component({selector:'rt-text-field',standalone:true,templateUrl:'./text-field.component.html',styleUrl:'./text-field.component.scss',changeDetection:ChangeDetectionStrategy.OnPush})
export class TextFieldComponent { label=input.required<string>(); value=input(''); type=input('text'); placeholder=input(''); disabled=input(false); valueChange=output<string>(); }
