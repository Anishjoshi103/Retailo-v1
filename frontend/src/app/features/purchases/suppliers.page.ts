import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { isValidGstinFormat } from '../settings/gst-states';
import { PurchasesApi } from './purchases.api';
import { Supplier } from './purchases.models';

const CREATING_ROLES: readonly string[] = ['owner', 'admin', 'manager'];
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type ActiveFilter = 'all' | 'active';

@Component({
  selector: 'app-suppliers-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './suppliers.page.html',
  styleUrl: './suppliers.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SuppliersPage {
  private readonly purchasesApi = inject(PurchasesApi);
  private readonly session = inject(SessionContextService);

  readonly suppliers = signal<readonly Supplier[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal('');
  readonly search = signal('');
  readonly filter = signal<ActiveFilter>('all');

  readonly canCreate = computed(() => this.session.roles().some((role) => CREATING_ROLES.includes(role)));

  // Add form
  readonly formOpen = signal(false);
  readonly name = signal('');
  readonly gstin = signal('');
  readonly phone = signal('');
  readonly email = signal('');
  readonly address = signal('');
  readonly saving = signal(false);
  readonly saveError = signal('');
  readonly serverErrors = signal<Readonly<Record<string, readonly string[]>>>({});
  readonly notice = signal('');

  readonly normalizedGstin = computed(() => this.gstin().trim().toUpperCase());
  readonly gstinError = computed(() => (this.normalizedGstin() && !isValidGstinFormat(this.normalizedGstin())
    ? 'Enter a GSTIN in the 15-character format, for example 27AAPFU0939F1ZV.' : ''));
  readonly emailError = computed(() => (this.email().trim() && !EMAIL_PATTERN.test(this.email().trim()) ? 'Enter a valid email address.' : ''));
  readonly canSave = computed(() => !this.saving() && this.name().trim().length > 0 && this.gstinError() === '' && this.emailError() === '');

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set('');
    this.purchasesApi.suppliers({
      ...(this.search().trim() ? { search: this.search().trim() } : {}),
      ...(this.filter() === 'active' ? { active: true } : {}),
    }).subscribe({
      next: (suppliers) => { this.suppliers.set(suppliers); this.loading.set(false); },
      error: () => { this.loadError.set('We could not load your suppliers. Check your connection and try again.'); this.loading.set(false); },
    });
  }

  setFilter(filter: ActiveFilter): void {
    this.filter.set(filter);
    this.load();
  }

  openForm(): void {
    this.formOpen.set(true);
    this.notice.set('');
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.saveError.set('');
    this.serverErrors.set({});
  }

  fieldError(field: string): string {
    return (this.serverErrors()[field] ?? []).join(' ');
  }

  save(): void {
    if (!this.canSave()) return;
    const gstin = this.normalizedGstin();
    const request = {
      name: this.name().trim(),
      ...(gstin ? { gstin } : {}),
      ...(this.phone().trim() ? { phone: this.phone().trim() } : {}),
      ...(this.email().trim() ? { email: this.email().trim() } : {}),
      ...(this.address().trim() ? { address: this.address().trim() } : {}),
    };
    this.saving.set(true);
    this.saveError.set('');
    this.serverErrors.set({});
    this.purchasesApi.createSupplier(request).subscribe({
      next: (supplier) => {
        this.saving.set(false);
        this.suppliers.update((all) => [supplier, ...all]);
        this.notice.set(`${supplier.name} was added.`);
        this.resetForm();
      },
      error: (error: unknown) => {
        this.saving.set(false);
        if (error instanceof ApiError && error.status === 400 && Object.keys(error.fieldErrors).length > 0) {
          this.serverErrors.set(error.fieldErrors);
        } else {
          this.saveError.set(this.describe(error));
        }
      },
    });
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  private resetForm(): void {
    this.formOpen.set(false);
    this.name.set('');
    this.gstin.set('');
    this.phone.set('');
    this.email.set('');
    this.address.set('');
  }

  private describe(error: unknown): string {
    if (error instanceof ApiError) {
      if (error.status === 0) return 'We could not reach the server. Try again.';
      if (error.status === 403) return 'Only a manager, administrator or the owner can add suppliers.';
      return error.message;
    }
    return 'The supplier could not be saved. Please try again.';
  }
}
