import { ChangeDetectionStrategy, Component, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { SessionContextService } from '../../core/auth/session-context.service';
import { SalesApi } from '../pos/sales.api';
import { SaleSummary } from '../pos/sales.models';

const PAGE_SIZE = 50;

@Component({
  selector: 'app-invoices-page',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './invoices.page.html',
  styleUrl: './invoices.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InvoicesPage {
  private readonly salesApi = inject(SalesApi);
  private readonly session = inject(SessionContextService);

  readonly invoiceNumber = signal('');
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly sales = signal<readonly SaleSummary[]>([]);
  readonly loading = signal(false);
  readonly loadingMore = signal(false);
  readonly hasMore = signal(false);
  readonly errorMessage = signal('');

  private requestId = 0;

  constructor() {
    // Reload whenever the cashier switches branch.
    effect(() => {
      this.session.selectedBranchId();
      untracked(() => this.reload());
    });
  }

  get dateRangeInvalid(): boolean {
    return !!this.dateFrom() && !!this.dateTo() && this.dateFrom() > this.dateTo();
  }

  reload(): void {
    if (this.dateRangeInvalid) return;
    this.fetch(0);
  }

  loadMore(): void {
    this.fetch(this.sales().length);
  }

  clearFilters(): void {
    this.invoiceNumber.set('');
    this.dateFrom.set('');
    this.dateTo.set('');
    this.reload();
  }

  private fetch(offset: number): void {
    const branchId = this.session.selectedBranchId();
    if (!branchId) { this.sales.set([]); this.hasMore.set(false); return; }
    const appending = offset > 0;
    const requestId = ++this.requestId;
    (appending ? this.loadingMore : this.loading).set(true);
    this.errorMessage.set('');
    this.salesApi.list({
      branchId,
      invoiceNumber: this.invoiceNumber().trim() || undefined,
      dateFrom: this.dateFrom() || undefined,
      dateTo: this.dateTo() || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .pipe(finalize(() => { if (requestId === this.requestId) (appending ? this.loadingMore : this.loading).set(false); }))
      .subscribe({
        next: (rows) => {
          if (requestId !== this.requestId) return; // a newer search superseded this one
          this.sales.set(appending ? [...this.sales(), ...rows] : rows);
          this.hasMore.set(rows.length === PAGE_SIZE);
        },
        error: () => {
          if (requestId !== this.requestId) return;
          if (!appending) { this.sales.set([]); this.hasMore.set(false); }
          this.errorMessage.set('We could not load invoices. Check your connection and try again.');
        },
      });
  }
}
