import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SessionContextService } from '../../core/auth/session-context.service';
import { SidenavComponent } from './sidenav.component';

describe('SidenavComponent', () => {
  function labelsFor(roles: readonly string[]): string[] {
    TestBed.configureTestingModule({
      imports: [SidenavComponent],
      providers: [provideRouter([]), { provide: SessionContextService, useValue: { roles: signal(roles) } }],
    });
    return TestBed.createComponent(SidenavComponent).componentInstance.visibleItems().map((item) => item.label);
  }

  it('shows Purchases to managers, admins and owners', () => {
    for (const role of ['manager', 'admin', 'owner']) {
      TestBed.resetTestingModule();
      expect(labelsFor([role]), role).toContain('Purchases');
    }
  });

  it('hides Purchases, Reports and Settings from cashiers', () => {
    const labels = labelsFor(['cashier']);
    expect(labels).toEqual(['Dashboard', 'Point of sale', 'Catalog', 'Inventory', 'GST & invoices']);
  });

  it('shows accountants the read-only sections only', () => {
    const labels = labelsFor(['accountant']);
    expect(labels).not.toContain('Purchases');
    expect(labels).not.toContain('Settings');
    expect(labels).toContain('GST & invoices');
    expect(labels).toContain('Reports');
  });
});
