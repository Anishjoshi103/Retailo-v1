import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { isValidGstinFormat } from '../settings/gst-states';
import { PurchasesApi } from './purchases.api';
import { Supplier, UpdateSupplierRequest } from './purchases.models';

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
  readonly pageOffset = signal(0);
  readonly pageSize = 50;
  readonly hasNextPage = signal(false);

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

  // Editing one supplier at a time
  readonly editingId = signal<string | null>(null);
  readonly editName = signal('');
  readonly editGstin = signal('');
  readonly editPhone = signal('');
  readonly editEmail = signal('');
  readonly editAddress = signal('');
  readonly editServerErrors = signal<Readonly<Record<string, readonly string[]>>>({});
  readonly confirmingId = signal<string | null>(null);
  readonly busyId = signal<string | null>(null);
  readonly rowMessage = signal<{ readonly id: string; readonly kind: 'ok' | 'error'; readonly text: string } | null>(null);

  readonly editGstinNormalized = computed(() => this.editGstin().trim().toUpperCase());
  readonly editGstinError = computed(() => (this.editGstinNormalized() && !isValidGstinFormat(this.editGstinNormalized())
    ? 'Enter a GSTIN in the 15-character format, for example 27AAPFU0939F1ZV.' : ''));
  readonly editEmailError = computed(() => (this.editEmail().trim() && !EMAIL_PATTERN.test(this.editEmail().trim()) ? 'Enter a valid email address.' : ''));

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set('');
    this.purchasesApi.suppliers({
      ...(this.search().trim() ? { search: this.search().trim() } : {}),
      ...(this.filter() === 'active' ? { active: true } : {}),
      limit: this.pageSize,
      offset: this.pageOffset(),
    }).subscribe({
      next: (suppliers) => { this.suppliers.set(suppliers); this.hasNextPage.set(suppliers.length === this.pageSize); this.loading.set(false); },
      error: () => { this.loadError.set('We could not load your suppliers. Check your connection and try again.'); this.loading.set(false); },
    });
  }

  setFilter(filter: ActiveFilter): void {
    this.filter.set(filter);
    this.pageOffset.set(0);
    this.load();
  }

  submitSearch(): void { this.pageOffset.set(0); this.load(); }

  previousPage(): void { this.pageOffset.update((offset) => Math.max(0, offset - this.pageSize)); this.load(); }

  nextPage(): void { if (!this.hasNextPage()) return; this.pageOffset.update((offset) => offset + this.pageSize); this.load(); }

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

  // ---- edit / deactivate
  startEdit(supplier: Supplier): void {
    this.confirmingId.set(null);
    this.editingId.set(supplier.id);
    this.editName.set(supplier.name);
    this.editGstin.set(supplier.gstin);
    this.editPhone.set(supplier.phone);
    this.editEmail.set(supplier.email);
    this.editAddress.set(supplier.address);
    this.editServerErrors.set({});
    this.rowMessage.set(null);
  }

  cancelEdit(): void {
    this.editingId.set(null);
    this.editServerErrors.set({});
  }

  editFieldError(field: string): string {
    return (this.editServerErrors()[field] ?? []).join(' ');
  }

  /** Only the fields that differ from the saved supplier, so nothing else is touched. */
  editChanges(supplier: Supplier): UpdateSupplierRequest {
    return {
      ...(this.editName().trim() !== supplier.name ? { name: this.editName().trim() } : {}),
      ...(this.editGstinNormalized() !== supplier.gstin ? { gstin: this.editGstinNormalized() } : {}),
      ...(this.editPhone().trim() !== supplier.phone ? { phone: this.editPhone().trim() } : {}),
      ...(this.editEmail().trim() !== supplier.email ? { email: this.editEmail().trim() } : {}),
      ...(this.editAddress().trim() !== supplier.address ? { address: this.editAddress().trim() } : {}),
    };
  }

  canSaveEdit(supplier: Supplier): boolean {
    return this.busyId() === null && this.editName().trim().length > 0 && this.editGstinError() === '' && this.editEmailError() === ''
      && Object.keys(this.editChanges(supplier)).length > 0;
  }

  saveEdit(supplier: Supplier): void {
    if (!this.canSaveEdit(supplier)) return;
    this.run(supplier, this.editChanges(supplier), `${this.editName().trim()} was updated.`, () => this.editingId.set(null), true);
  }

  askDeactivate(supplier: Supplier): void {
    this.editingId.set(null);
    this.confirmingId.set(supplier.id);
    this.rowMessage.set(null);
  }

  cancelDeactivate(): void {
    this.confirmingId.set(null);
  }

  deactivate(supplier: Supplier): void {
    this.run(supplier, { is_active: false }, `${supplier.name} was deactivated.`, () => this.confirmingId.set(null));
  }

  reactivate(supplier: Supplier): void {
    this.run(supplier, { is_active: true }, `${supplier.name} is active again.`);
  }

  private run(supplier: Supplier, request: UpdateSupplierRequest, success: string, done?: () => void, isEdit = false): void {
    if (this.busyId() !== null) return;
    this.busyId.set(supplier.id);
    this.rowMessage.set(null);
    this.editServerErrors.set({});
    this.purchasesApi.updateSupplier(supplier.id, request).subscribe({
      next: (updated) => {
        this.busyId.set(null);
        this.suppliers.update((all) => all.map((item) => (item.id === updated.id ? updated : item)));
        this.rowMessage.set({ id: supplier.id, kind: 'ok', text: success });
        done?.();
      },
      error: (error: unknown) => {
        this.busyId.set(null);
        if (isEdit && error instanceof ApiError && error.status === 400 && Object.keys(error.fieldErrors).length > 0) {
          this.editServerErrors.set(error.fieldErrors);
        } else {
          this.rowMessage.set({ id: supplier.id, kind: 'error', text: this.describe(error) });
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
      if (error.status === 403) return 'Only a manager, administrator or the owner can change suppliers.';
      return error.message;
    }
    return 'The supplier could not be saved. Please try again.';
  }
}
