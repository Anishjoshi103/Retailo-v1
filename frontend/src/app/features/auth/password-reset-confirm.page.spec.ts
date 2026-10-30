import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { PasswordResetConfirmPage } from './password-reset-confirm.page';

describe('PasswordResetConfirmPage', () => {
  let http: HttpTestingController;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PasswordResetConfirmPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([]),
        { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: { get: (key: string) => key === 'uid' ? 'encoded-uid' : key === 'token' ? 'reset-token' : null } } } }],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());
  it('requires matching strong passwords before sending a request', () => {
    const fixture = TestBed.createComponent(PasswordResetConfirmPage);
    fixture.detectChanges();
    fixture.componentInstance.form.controls.password.setValue('Strong-password-123');
    fixture.componentInstance.form.controls.confirmPassword.setValue('different-password');
    fixture.componentInstance.submit();
    expect(fixture.componentInstance.submitting()).toBe(false);
    http.expectNone('/api/v1/auth/password-reset/confirm');
  });
  it('posts reset credentials and shows success', () => {
    const fixture = TestBed.createComponent(PasswordResetConfirmPage);
    fixture.detectChanges();
    fixture.componentInstance.form.controls.password.setValue('Strong-password-123');
    fixture.componentInstance.form.controls.confirmPassword.setValue('Strong-password-123');
    fixture.componentInstance.submit();
    const request = http.expectOne('/api/v1/auth/password-reset/confirm');
    expect(request.request.body).toEqual({ uid: 'encoded-uid', token: 'reset-token', password: 'Strong-password-123' });
    request.flush({ detail: 'Password reset successfully. You can now sign in.' });
    expect(fixture.componentInstance.successMessage()).toContain('Password reset successfully');
  });
});
