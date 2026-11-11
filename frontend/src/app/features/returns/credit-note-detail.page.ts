import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { switchMap, tap } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { ReturnsApi } from './returns.api';
import { CreditNote } from './returns.models';

@Component({
  selector: 'app-credit-note-detail-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './credit-note-detail.page.html',
  styleUrl: './credit-note-detail.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CreditNoteDetailPage {
  private readonly returnsApi = inject(ReturnsApi);
  private readonly route = inject(ActivatedRoute);

  readonly note = signal<CreditNote | null>(null);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly errorMessage = signal('');

  constructor() {
    this.route.paramMap
      .pipe(
        tap(() => { this.loading.set(true); this.note.set(null); this.notFound.set(false); this.errorMessage.set(''); }),
        switchMap((params) => this.returnsApi.get(params.get('id') ?? '')),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe({ next: (note) => { this.note.set(note); this.loading.set(false); }, error: (error: unknown) => this.fail(error) });
  }

  hasIgst(note: CreditNote): boolean {
    return Number(note.igst_total) !== 0;
  }

  print(): void {
    window.print();
  }

  private fail(error: unknown): void {
    this.loading.set(false);
    if (error instanceof ApiError && error.status === 404) this.notFound.set(true);
    else this.errorMessage.set('We could not load this credit note. Check your connection and try again.');
  }
}
