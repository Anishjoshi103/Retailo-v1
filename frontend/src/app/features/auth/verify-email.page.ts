import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { APP_CONFIG } from '../../core/config/app-config.token';

@Component({ selector: 'retailo-verify-email-page', standalone: true, imports: [RouterLink], templateUrl: './verify-email.page.html', styleUrl: './auth-form.page.scss', changeDetection: ChangeDetectionStrategy.OnPush })
export class VerifyEmailPage {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly config = inject(APP_CONFIG);
  readonly loading = signal(true);
  readonly success = signal(false);
  readonly message = signal('Verifying your email address…');

  constructor() {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) { this.loading.set(false); this.message.set('This verification link is missing its token. Request a new registration email or contact support.'); return; }
    this.http.post<{ detail: string }>(this.config.apiBaseUrl.replace(/\/$/, '') + '/auth/verify-email', { token }).subscribe({
      next: (result) => { this.success.set(true); this.message.set(result.detail || 'Email verified. You can now sign in.'); },
      error: (error: unknown) => { this.message.set(error instanceof HttpErrorResponse && error.status === 0 ? 'Unable to reach Retailo. Check your connection and try again.' : 'This verification link is invalid or expired. Request a new registration email or contact support.'); },
    }).add(() => this.loading.set(false));
  }
}
