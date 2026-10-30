import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { HomePage } from './home.page';

describe('HomePage', () => {
  it('renders the Retailo workspace heading and planned modules', async () => {
    await TestBed.configureTestingModule({ imports: [HomePage] }).compileComponents();
    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('A clearer view of your store.');
    expect(fixture.nativeElement.textContent).toContain('Point of sale');
    expect(fixture.nativeElement.textContent).toContain('Inventory');
    expect(fixture.nativeElement.textContent).toContain('GST & reports');
  });
});
