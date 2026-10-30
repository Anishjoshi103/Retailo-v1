import { HttpBackend, HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { catchError, finalize, map, Observable, of, shareReplay, tap } from 'rxjs';
import { APP_CONFIG } from '../config/app-config.token';

interface RefreshResponse { readonly access: string; }

@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly config = inject(APP_CONFIG);
  private readonly rawHttp = new HttpClient(inject(HttpBackend));
  private readonly token = signal<string | null>(null);
  private refreshing: Observable<string | null> | null = null;
  private loggingOut: Observable<void> | null = null;
  readonly accessToken = this.token.asReadonly();

  setAccessToken(value: string | null): void { this.token.set(value); }

  refreshAccessToken(): Observable<string | null> {
    if (this.refreshing) return this.refreshing;
    this.refreshing = this.rawHttp.post<RefreshResponse>(this.authUrl('refresh'), {}, { withCredentials: true }).pipe(
      map((result) => {
        if (!result?.access) throw new Error('Refresh response did not include an access token.');
        return result.access;
      }),
      tap((value) => this.setAccessToken(value)),
      catchError(() => { this.setAccessToken(null); return of(null); }),
      finalize(() => { this.refreshing = null; }),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.refreshing;
  }

  logout(): Observable<void> {
    if (this.loggingOut) return this.loggingOut;
    this.setAccessToken(null);
    this.loggingOut = this.rawHttp.post<void>(this.authUrl('logout'), {}, { withCredentials: true }).pipe(
      catchError(() => of(void 0)),
      tap(() => this.setAccessToken(null)),
      finalize(() => { this.loggingOut = null; }),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.loggingOut;
  }

  clearSession(): void { this.setAccessToken(null); }

  private authUrl(endpoint: string): string {
    return `${this.config.apiBaseUrl.replace(/\\/$/, '')}/auth/${endpoint}`;
  }
}
