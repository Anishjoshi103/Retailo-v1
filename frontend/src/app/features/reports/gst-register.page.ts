import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { SessionContextService } from '../../core/auth/session-context.service';
import { FileSaver } from '../../core/files/file-saver.service';
import { DateRange, Preset, presetRange } from './date-range';
import { ReportsApi } from './reports.api';
import { GstRegister, GstTable } from './reports.models';

type Range = Extract<Preset, 'month' | 'lastMonth'> | 'custom';
type Scope = 'branch' | 'all';

const MAX_RANGE_DAYS = 366;

@Component({
  selector: 'app-gst-register-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './gst-register.page.html',
  styleUrl: './gst-register.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GstRegisterPage {
  private readonly reportsApi = inject(ReportsApi);
  private readonly session = inject(SessionContextService);
  private readonly fileSaver = inject(FileSaver);

  /** Returns are normally filed for the previous month, so that is the starting point. */
  readonly range = signal<Range>('lastMonth');
  readonly customFrom = signal('');
  readonly customTo = signal('');
  readonly scope = signal<Scope>('branch');
  readonly register = signal<GstRegister | null>(null);
  readonly loading = signal(false);
  readonly errorMessage = signal('');
  readonly downloading = signal<GstTable | null>(null);
  readonly downloadError = signal('');

  private requestId = 0;

  readonly dates = computed<DateRange | null>(() => {
    if (this.range() !== 'custom') return presetRange(this.range() as Preset, new Date());
    return this.customFrom() && this.customTo() && this.customFrom() <= this.customTo()
      ? { dateFrom: this.customFrom(), dateTo: this.customTo() } : null;
  });

  readonly customProblem = computed(() => {
    if (this.range() !== 'custom') return '';
    const from = this.customFrom();
    const to = this.customTo();
    if (!from || !to) return 'Choose both a start and an end date.';
    if (from > to) return 'The start date is after the end date.';
    return Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000) + 1 > MAX_RANGE_DAYS ? `Choose a range of at most ${MAX_RANGE_DAYS} days.` : '';
  });

  readonly hasData = computed(() => {
    const register = this.register();
    return !!register && (register.rates.length > 0 || register.hsn.length > 0 || register.documents.length > 0);
  });

  constructor() {
    // Reload whenever the branch changes.
    effect(() => {
      this.session.selectedBranchId();
      untracked(() => this.load());
    });
  }

  choose(range: Range): void {
    this.range.set(range);
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
    if (this.scope() === 'branch' && !branchId) { this.register.set(null); return; }
    const requestId = ++this.requestId;
    this.loading.set(true);
    this.errorMessage.set('');
    this.reportsApi.gstRegister({ ...dates, ...(branchId ? { branchId } : {}) })
      .pipe(finalize(() => { if (requestId === this.requestId) this.loading.set(false); }))
      .subscribe({
        next: (register) => { if (requestId === this.requestId) this.register.set(register); },
        error: () => {
          if (requestId !== this.requestId) return;
          this.register.set(null);
          this.errorMessage.set('We could not load the GST register. Check your connection and try again.');
        },
      });
  }

  /** Download one table for exactly the period and branches shown on screen. */
  download(table: GstTable): void {
    const register = this.register();
    if (!register || this.downloading() !== null) return;
    this.downloading.set(table);
    this.downloadError.set('');
    this.reportsApi.gstRegisterCsv(table, {
      dateFrom: register.date_from, dateTo: register.date_to, ...(register.branch_id ? { branchId: register.branch_id } : {}),
    }).pipe(finalize(() => this.downloading.set(null))).subscribe({
      next: (blob) => this.fileSaver.save(blob, `gst-${table}-${register.date_from}-to-${register.date_to}.csv`),
      error: () => this.downloadError.set('We could not download that file. Try again.'),
    });
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }
}
