import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { SessionContextService } from '../../core/auth/session-context.service';
import { SessionService } from '../../core/auth/session.service';
import { TopbarComponent } from './topbar.component';

describe('TopbarComponent', () => {
  it('clears session context and navigates to login after logout completes', async () => {
    const logout = vi.fn(() => of(void 0));
    const clear = vi.fn();
    await TestBed.configureTestingModule({
      imports: [TopbarComponent],
      providers: [
        provideRouter([]),
        { provide: SessionService, useValue: { logout } },
        { provide: SessionContextService, useValue: { clear } },
      ],
    }).overrideComponent(TopbarComponent, { set: { template: '' } }).compileComponents();

    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(TopbarComponent);

    fixture.componentInstance.signOut();

    expect(logout).toHaveBeenCalledOnce();
    expect(clear).toHaveBeenCalledOnce();
    expect(navigate).toHaveBeenCalledWith(['/auth/login']);
    fixture.destroy();
  });
});
