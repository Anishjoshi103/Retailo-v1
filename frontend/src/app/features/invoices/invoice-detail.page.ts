import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { switchMap, tap } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { SalesApi } from '../pos/sales.api';
import { Sale } from '../pos/sales.models';
import { ReturnsApi } from '../returns/returns.api';
import { CreditNoteSummary } from '../returns/returns.models';

const RETURNING_ROLES: readonly string[] = ['owner', 'admin', 'manager', 'cashier'];

@Component({
  selector: 'app-invoice-detail-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './invoice-detail.page.html',
  styleUrl: './invoice-detail.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InvoiceDetailPage {
  private readonly salesApi = inject(SalesApi);
  private readonly returnsApi = inject(ReturnsApi);
  private readonly session = inject(SessionContextService);
  private readonly route = inject(ActivatedRoute);

  readonly sale = signal<Sale | null>(null);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly errorMessage = signal('');
  readonly creditNotes = signal<readonly CreditNoteSummary[]>([]);

  constructor() {
    this.route.paramMap
      .pipe(
        tap(() => { this.loading.set(true); this.sale.set(null); this.notFound.set(false); this.errorMessage.set(''); this.creditNotes.set([]); }),
        switchMap((params) => this.salesApi.get(params.get('id') ?? '')),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe({
        next: (sale) => { this.sale.set(sale); this.loading.set(false); this.loadCreditNotes(sale.id); },
        error: (error: unknown) => this.fail(error),
      });
  }

  hasIgst(sale: Sale): boolean {
    return Number(sale.igst_total) !== 0;
  }

  /** True when the caller may take returns and some quantity on the invoice is still returnable. */
  canReturn(sale: Sale): boolean {
    return this.session.roles().some((role) => RETURNING_ROLES.includes(role))
      && sale.lines.some((line) => Number(line.quantity) - Number(line.returned_quantity) > 0);
  }

  hasReturns(sale: Sale): boolean {
    return sale.lines.some((line) => Number(line.returned_quantity) > 0);
  }

  print(): void {
    window.print();
  }

  private loadCreditNotes(saleId: string): void {
    // Supplementary: a failure here must not hide the invoice itself.
    this.returnsApi.list({ saleId }).subscribe({ next: (notes) => this.creditNotes.set(notes), error: () => undefined });
  }

  private fail(error: unknown): void {
    this.loading.set(false);
    if (error instanceof ApiError && error.status === 404) this.notFound.set(true);
    else this.errorMessage.set('We could not load this invoice. Check your connection and try again.');
  }
}
