import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ApiError } from '../../core/api/api-error.model';
import { BranchesApi, BranchGst } from './branches.api';
import { branchCodeProblem, GST_STATES, isValidGstinFormat, stateName } from './gst-states';

interface BranchDraft {
  readonly gstin: string;
  readonly stateCode: string;
}

type SaveState = { readonly kind: 'saving' } | { readonly kind: 'saved' } | { readonly kind: 'error'; readonly message: string };

@Component({
  selector: 'app-settings-page',
  standalone: true,
  templateUrl: './settings.page.html',
  styleUrl: './settings.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsPage {
  private readonly branchesApi = inject(BranchesApi);

  readonly states = GST_STATES;
  readonly stateName = stateName;
  readonly branches = signal<readonly BranchGst[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal('');
  /** Unsaved edits per branch id; a branch without a draft shows its saved values. */
  readonly drafts = signal<Readonly<Record<string, BranchDraft>>>({});
  readonly saves = signal<Readonly<Record<string, SaveState>>>({});

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set('');
    this.branchesApi.list().subscribe({
      next: (branches) => { this.branches.set(branches); this.drafts.set({}); this.loading.set(false); },
      error: () => { this.loadError.set('We could not load your branches. Check your connection and try again.'); this.loading.set(false); },
    });
  }

  draft(branch: BranchGst): BranchDraft {
    return this.drafts()[branch.id] ?? { gstin: branch.gstin, stateCode: branch.state_code };
  }

  setGstin(branch: BranchGst, value: string): void {
    const gstin = value.trim().toUpperCase();
    const current = this.draft(branch);
    // A valid GSTIN fixes the state: its first two digits are the state code.
    const derived = isValidGstinFormat(gstin) ? gstin.slice(0, 2) : current.stateCode;
    this.setDraft(branch, { gstin, stateCode: derived });
  }

  setState(branch: BranchGst, stateCode: string): void {
    this.setDraft(branch, { ...this.draft(branch), stateCode });
  }

  gstinError(branch: BranchGst): string {
    const { gstin, stateCode } = this.draft(branch);
    if (!gstin) return '';
    if (!isValidGstinFormat(gstin)) return 'Enter a GSTIN in the 15-character format, for example 27AAPFU0939F1ZV.';
    if (stateCode && gstin.slice(0, 2) !== stateCode) return `The GSTIN starts with ${gstin.slice(0, 2)} (${stateName(gstin.slice(0, 2)) || 'unknown state'}), which does not match the selected state.`;
    return '';
  }

  codeProblem(branch: BranchGst): string {
    return branchCodeProblem(branch.code);
  }

  dirty(branch: BranchGst): boolean {
    const draft = this.draft(branch);
    return draft.gstin !== branch.gstin || draft.stateCode !== branch.state_code;
  }

  canSave(branch: BranchGst): boolean {
    return this.dirty(branch) && this.gstinError(branch) === '' && this.saves()[branch.id]?.kind !== 'saving';
  }

  /** A branch can bill once it has a state code and a branch code that fits an invoice number. */
  ready(branch: BranchGst): boolean {
    return branch.state_code !== '' && this.codeProblem(branch) === '';
  }

  save(branch: BranchGst): void {
    if (!this.canSave(branch)) return;
    const { gstin, stateCode } = this.draft(branch);
    this.setSave(branch.id, { kind: 'saving' });
    this.branchesApi.updateGst(branch.id, { gstin, state_code: stateCode }).subscribe({
      next: (updated) => {
        this.branches.update((all) => all.map((item) => (item.id === updated.id ? updated : item)));
        this.drafts.update((all) => Object.fromEntries(Object.entries(all).filter(([id]) => id !== updated.id)));
        this.setSave(branch.id, { kind: 'saved' });
      },
      error: (error: unknown) => this.setSave(branch.id, { kind: 'error', message: this.describeError(error) }),
    });
  }

  saveState(branch: BranchGst): SaveState | undefined {
    return this.saves()[branch.id];
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  private setDraft(branch: BranchGst, draft: BranchDraft): void {
    this.drafts.update((all) => ({ ...all, [branch.id]: draft }));
    this.saves.update((all) => Object.fromEntries(Object.entries(all).filter(([id]) => id !== branch.id)));
  }

  private setSave(branchId: string, state: SaveState): void {
    this.saves.update((all) => ({ ...all, [branchId]: state }));
  }

  private describeError(error: unknown): string {
    if (error instanceof ApiError) {
      if (error.status === 0) return 'We could not reach the server. Try again.';
      if (error.status === 403) return 'Only the store owner or an administrator can change GST details.';
      const details = Object.values(error.fieldErrors).flat();
      return details.length > 0 ? details.join(' ') : error.message;
    }
    return 'The change could not be saved. Please try again.';
  }
}
