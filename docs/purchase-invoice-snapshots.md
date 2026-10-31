# Purchase invoice and GRN matching foundation

## Relationship decision

A supplier invoice is a separate commercial/tax document from a goods receipt note (GRN). One invoice may cover several GRNs, and one GRN may be billed across several invoices. The relationship is represented by allocations from invoice lines to receipt lines; there is deliberately no single GRN foreign key on the invoice header.

## Model contract

- **PurchaseInvoice** holds the supplier invoice identity and immutable supplier/GST/place-of-supply snapshots, document date, idempotency metadata, status, and reconciled totals.
- **PurchaseInvoiceLine** holds the supplier's billed product/quantity/price and a tax snapshot calculated by the GST foundation.
- **PurchaseInvoiceAllocation** maps a billed line to a received GRN line, with allocated quantity and taxable value. This supports consolidated invoices and partial billing.
- All records are tenant-owned. Application services must scope every read through `.objects.for_tenant(tenant_id)` and verify that supplier, invoice, branch, product, and GRN line belong to the same tenant. Allocations must also respect the invoice's branch/place-of-supply registration context.
- An invoice's supplier invoice number must be unique for a tenant and supplier when non-empty. Idempotency keys are unique per tenant.
- Allocated quantity may not exceed the GRN line's received quantity across all invoices. The check must lock the GRN line and existing allocations inside a transaction; it cannot safely be enforced by a model-level aggregate check alone.
- An invoice can be drafted and reconciled before posting. Once posted, its header, lines, and allocations are immutable. Corrections require a reversal/credit-note workflow.
- GST calculations use `apps.gst.tax.calculate_gst`; calculated components and totals are stored as decimal strings at API boundaries and Decimal values in the database. No float arithmetic.
- GRN stock movements remain inventory-only. Invoice creation does not change stock; supplier balances, input-tax-credit ledgers, and accounting journal entries are out of scope for this foundation.

## Explicit non-goals

This foundation does not infer place of supply from a GSTIN, verify GSTIN against GSTN, decide input-tax-credit eligibility, or resolve the still-open tenant GSTIN/branch-registration mapping policy. Those require explicit product/accounting decisions before posting financial entries.
