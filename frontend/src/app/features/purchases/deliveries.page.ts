import { ChangeDetectionStrategy, Component, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { SessionContextService } from '../../core/auth/session-context.service';
import { PurchasesApi } from './purchases.api';
import { ReceiptSummary } from './purchases.models';

const PAGE_SIZE = 50;

@Component({
  selector: 'app-deliveries-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './deliveries.page.html',
  styleUrl: './deliveries.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DeliveriesPage {
  private readonly purchasesApi = inject(PurchasesApi);
  private readonly session = inject(SessionContextService);

  readonly invoiceNumber = signal('');
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly deliveries = signal<readonly ReceiptSummary[]>([]);
  readonly loading = signal(false);
  readonly loadingMore = signal(false);
  readonly hasMore = signal(false);
  readonly errorMessage = signal('');

  private requestId = 0;

  constructor() {
    // Reload whenever the branch changes.
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
    this.fetch(this.deliveries().length);
  }

  clearFilters(): void {
    this.invoiceNumber.set('');
    this.dateFrom.set('');
    this.dateTo.set('');
    this.reload();
  }

  day(iso: string): string {
    return iso.slice(0, 10);
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  private fetch(offset: number): void {
    const branchId = this.session.selectedBranchId();
    if (!branchId) { this.deliveries.set([]); this.hasMore.set(false); return; }
    const appending = offset > 0;
    const requestId = ++this.requestId;
    (appending ? this.loadingMore : this.loading).set(true);
    this.errorMessage.set('');
    this.purchasesApi.receipts({
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
          this.deliveries.set(appending ? [...this.deliveries(), ...rows] : rows);
          this.hasMore.set(rows.length === PAGE_SIZE);
        },
        error: () => {
          if (requestId !== this.requestId) return;
          if (!appending) { this.deliveries.set([]); this.hasMore.set(false); }
          this.errorMessage.set('We could not load deliveries. Check your connection and try again.');
        },
      });
  }
}
