import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { APP_CONFIG } from '../../core/config/app-config.token';

@Component({ selector: 'retailo-password-reset-confirm-page', standalone: true, imports: [ReactiveFormsModule, RouterLink], templateUrl: './password-reset-confirm.page.html', styleUrl: './auth-form.page.scss', changeDetection: ChangeDetectionStrategy.OnPush })
export class PasswordResetConfirmPage {
  private readonly fb = inject(FormBuilder);
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly config = inject(APP_CONFIG);
  readonly submitting = signal(false);
  readonly errorMessage = signal('');
  readonly successMessage = signal('');
  readonly form = this.fb.nonNullable.group({ password: ['', [Validators.required, Validators.minLength(12)]], confirmPassword: ['', [Validators.required]] });

  submit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    if (this.form.controls.password.value !== this.form.controls.confirmPassword.value) {
      this.form.controls.confirmPassword.setErrors({ mismatch: true }); this.form.controls.confirmPassword.markAsTouched(); return;
    }
    const uid = this.route.snapshot.queryParamMap.get('uid');
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!uid || !token) { this.errorMessage.set('This password reset link is incomplete or invalid. Request a new reset email.'); return; }
    this.submitting.set(true); this.errorMessage.set(''); this.successMessage.set('');
    this.http.post<{ detail: string }>(this.config.apiBaseUrl.replace(/\/$/, '') + '/auth/password-reset/confirm', { uid, token, password: this.form.controls.password.value }).subscribe({
      next: (result) => { this.successMessage.set(result.detail || 'Password reset successfully. You can now sign in.'); this.form.reset(); },
      error: (error: unknown) => { this.errorMessage.set(error instanceof HttpErrorResponse && error.status === 0 ? 'Unable to reach Retailo. Check your connection and try again.' : 'This password reset link is invalid or expired. Request a new one.'); },
    }).add(() => this.submitting.set(false));
  }
}
