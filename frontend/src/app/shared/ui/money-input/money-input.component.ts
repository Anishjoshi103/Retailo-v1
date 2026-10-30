import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
@Component({selector:'rt-money-input',standalone:true,templateUrl:'./money-input.component.html',styleUrl:'./money-input.component.scss',changeDetection:ChangeDetectionStrategy.OnPush})
export class MoneyInputComponent {
  label = input.required<string>();
  value = input('');
  valueChange = output<string>();

  onInput(raw: string): void {
    const cleaned = raw.replace(/[^0-9.]/g, '');
    const dot = cleaned.indexOf('.');
    const normalized = dot < 0 ? cleaned : cleaned.slice(0, dot + 1) + cleaned.slice(dot + 1).replace(/\./g, '');
    this.valueChange.emit(normalized);
  }
}
