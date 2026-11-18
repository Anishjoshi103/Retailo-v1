import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { finalize } from 'rxjs';
import { SessionContextService } from '../../core/auth/session-context.service';
import { formatRupees, parseMoney } from '../pos/money';
import { DateRange, Preset, presetRange } from './date-range';
import { ReportsApi } from './reports.api';
import { SalesSummary } from './reports.models';

type Range = Preset | 'custom';
type Scope = 'branch' | 'all';

const MAX_RANGE_DAYS = 366;

const PRESETS: readonly { readonly value: Preset; readonly label: string }[] = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'week', label: 'Last 7 days' },
  { value: 'month', label: 'This month' },
];

const METHOD_LABELS: Readonly<Record<string, string>> = { cash: 'Cash', upi: 'UPI', card: 'Card', other: 'Other' };

@Component({
  selector: 'app-reports-page',
  standalone: true,
  templateUrl: './reports.page.html',
  styleUrl: './reports.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReportsPage {
  private readonly reportsApi = inject(ReportsApi);
  private readonly session = inject(SessionContextService);

  readonly presets = PRESETS;
  readonly rupees = formatRupees;

  readonly range = signal<Range>('today');
  readonly customFrom = signal('');
  readonly customTo = signal('');
  readonly scope = signal<Scope>('branch');
  readonly summary = signal<SalesSummary | null>(null);
  readonly loading = signal(false);
  readonly errorMessage = signal('');

  private requestId = 0;

  /** The dates to ask for, or null while a custom range is incomplete or invalid. */
  readonly dates = computed<DateRange | null>(() => {
    if (this.range() !== 'custom') return presetRange(this.range() as Preset, new Date());
    const from = this.customFrom();
    const to = this.customTo();
    return from && to && from <= to ? { dateFrom: from, dateTo: to } : null;
  });

  readonly customProblem = computed(() => {
    if (this.range() !== 'custom') return '';
    const from = this.customFrom();
    const to = this.customTo();
    if (!from || !to) return 'Choose both a start and an end date.';
    if (from > to) return 'The start date is after the end date.';
    const days = Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000) + 1;
    return days > MAX_RANGE_DAYS ? `Choose a range of at most ${MAX_RANGE_DAYS} days.` : '';
  });

  /** Cash taken from customers, less cash refunded to them (refunds are always cash). */
  readonly cashInHandPaise = computed(() => {
    const summary = this.summary();
    if (!summary) return 0;
    const cash = parseMoney(summary.payments.find((payment) => payment.method === 'cash')?.amount ?? '0') ?? 0;
    return cash - (parseMoney(summary.returns.grand_total) ?? 0);
  });

  readonly hasActivity = computed(() => {
    const summary = this.summary();
    return !!summary && (summary.sales.count > 0 || summary.returns.count > 0);
  });

  constructor() {
    // Reload whenever the branch changes.
    effect(() => {
      this.session.selectedBranchId();
      untracked(() => this.load());
    });
  }

  choosePreset(preset: Preset): void {
    this.range.set(preset);
    this.load();
  }

  chooseCustom(): void {
    this.range.set('custom');
    this.load();
  }

  setScope(scope: Scope): void {
    this.scope.set(scope);
    this.load();
  }

  load(): void {
    const dates = this.dates();
    if (this.customProblem() !== '' || dates === null) return;
    const branchId = this.scope() === 'branch' ? this.session.selectedBranchId() : null;
    if (this.scope() === 'branch' && !branchId) { this.summary.set(null); return; }
    const requestId = ++this.requestId;
    this.loading.set(true);
    this.errorMessage.set('');
    this.reportsApi.salesSummary({ ...dates, ...(branchId ? { branchId } : {}) })
      .pipe(finalize(() => { if (requestId === this.requestId) this.loading.set(false); }))
      .subscribe({
        next: (summary) => { if (requestId === this.requestId) this.summary.set(summary); },
        error: () => {
          if (requestId !== this.requestId) return;
          this.summary.set(null);
          this.errorMessage.set('We could not load the report. Check your connection and try again.');
        },
      });
  }

  methodLabel(method: string): string {
    return METHOD_LABELS[method] ?? method;
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }
}
