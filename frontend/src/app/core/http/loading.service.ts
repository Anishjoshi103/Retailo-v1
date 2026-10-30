import { Injectable, signal } from '@angular/core';
@Injectable({ providedIn: 'root' })
export class LoadingService {
  private readonly count = signal(0);
  readonly isLoading = this.count.asReadonly();
  begin(): void { this.count.update((value) => value + 1); }
  end(): void { this.count.update((value) => Math.max(0, value - 1)); }
}