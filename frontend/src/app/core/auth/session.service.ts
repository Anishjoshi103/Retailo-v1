import { HttpBackend, HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { catchError, finalize, map, Observable, of, shareReplay, tap } from 'rxjs';
import { APP_CONFIG } from '../config/app-config.token';
interface RefreshResponse { readonly access: string; }
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly config = inject(APP_CONFIG); private readonly rawHttp = new HttpClient(inject(HttpBackend));
  private readonly token = signal<string | null>(null); private refreshing: Observable<string | null> | null = null;
  readonly accessToken = this.token.asReadonly();
  setAccessToken(value: string | null): void { this.token.set(value); }
  refreshAccessToken(): Observable<string | null> {
    if (this.refreshing) return this.refreshing;
    this.refreshing = this.rawHttp.post<RefreshResponse>(`${this.config.apiBaseUrl.replace(/\/$/, '')}/auth/refresh`, {}, { withCredentials: true }).pipe(
      map((result) => result.access), tap((value) => this.setAccessToken(value)),
      catchError(() => { this.setAccessToken(null); return of(null); }),
      finalize(() => { this.refreshing = null; }), shareReplay({ bufferSize: 1, refCount: false })
    );
    return this.refreshing;
  }
  clearSession(): void { this.setAccessToken(null); }
}