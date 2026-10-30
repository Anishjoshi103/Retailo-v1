# Retailo shared UI kit

Standalone Angular components in `frontend/src/app/shared/ui`. Import the component directly or use the barrel at `shared/ui/index.ts`. Components use external templates/styles and global design tokens; no third-party UI library is required.

## Components

- `ButtonComponent`: labelled primary, secondary, or danger action; supports disabled and button type.
- `IconButtonComponent`: icon slot with required accessible label.
- `TextFieldComponent`: labelled text input; bind `value` and listen to `valueChange`.
- `SelectComponent`: labelled select with typed `SelectOption[]`.
- `MoneyInputComponent`: emits a decimal string; never converts money to a JavaScript number. Persist/validate the value with backend Decimal rules. Formatting and Indian digit grouping should be applied by the caller for display-only values.
- `DataTableComponent`: typed columns/rows, client-side sortable columns, page navigation, and loading/error/empty states.
- `DialogComponent`: conditional modal surface with labelled dialog semantics and close output. Integrating screens should manage focus return and Escape handling.
- `ToastComponent`: status message with dismiss output.
- `EmptyStateComponent`: title, description, and optional projected action.
- `SkeletonComponent`: decorative placeholder; respects reduced-motion preferences.
- `BadgeComponent`: neutral/success/warning/danger status.
- `KbdComponent`: semantic keyboard shortcut hint.

## Example

```ts
import { ButtonComponent, MoneyInputComponent } from './shared/ui';
```

```html
<rt-money-input label="Unit price" [value]="unitPrice" (valueChange)="unitPrice = $event" />
<rt-button label="Save" (click)="save()" />
```

Money values remain strings at the UI boundary. Do not use `Number`, `parseFloat`, or floating-point arithmetic for invoice totals, tax, or quantities. Server-side Decimal calculations remain authoritative.
