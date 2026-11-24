import getpass
import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Product
from apps.inventory.models import InventoryBalance, StockMovement, Supplier
from apps.tenancy.models import Branch, BranchAccess, Membership, Tenant

DEMO_TENANT_SLUG = "retailo-demo"
DEMO_TENANT_NAME = "Retailo Demo Store"
DEFAULT_OWNER_EMAIL = "owner@retailo-demo.local"
OPENING_QUANTITY = Decimal("50.000")

BRANCHES = (
    {"code": "MAIN", "name": "Main Store"},
    {"code": "WH", "name": "Warehouse"},
)
PRODUCTS = (
    {
        "sku": "DEMO-RICE-001",
        "name": "Premium Basmati Rice 1 kg",
        "unit": Product.Unit.KG,
        "hsn_code": "10063020",
        "gst_rate": Decimal("5.00"),
        "selling_price": Decimal("120.00"),
        "purchase_price": Decimal("95.00"),
    },
    {
        "sku": "DEMO-MILK-001",
        "name": "Toned Milk 1 L",
        "unit": Product.Unit.L,
        "hsn_code": "04012000",
        "gst_rate": Decimal("5.00"),
        "selling_price": Decimal("60.00"),
        "purchase_price": Decimal("48.00"),
    },
    {
        "sku": "DEMO-OIL-001",
        "name": "Cooking Oil 1 L",
        "unit": Product.Unit.L,
        "hsn_code": "15079010",
        "gst_rate": Decimal("5.00"),
        "selling_price": Decimal("155.00"),
        "purchase_price": Decimal("125.00"),
    },
    {
        "sku": "DEMO-SOAP-001",
        "name": "Bathing Soap 100 g",
        "unit": Product.Unit.EACH,
        "hsn_code": "34011190",
        "gst_rate": Decimal("18.00"),
        "selling_price": Decimal("40.00"),
        "purchase_price": Decimal("28.00"),
    },
    {
        "sku": "DEMO-BISCUIT-001",
        "name": "Glucose Biscuits 200 g",
        "unit": Product.Unit.PACK,
        "hsn_code": "19053100",
        "gst_rate": Decimal("18.00"),
        "selling_price": Decimal("30.00"),
        "purchase_price": Decimal("21.00"),
    },
)


class Command(BaseCommand):
    help = "Create repeatable demo data for one isolated Retailo demo store."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEFAULT_OWNER_EMAIL)
        parser.add_argument(
            "--state-code",
            default="27",
            help="Two-digit GST state code (default: 27, Maharashtra).",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        state_code = options["state_code"].strip()
        if not email or "@" not in email:
            raise CommandError("Provide a valid email using --email.")
        if len(state_code) != 2 or not state_code.isdigit():
            raise CommandError("--state-code must contain exactly two digits.")

        with transaction.atomic():
            tenant, created = Tenant.objects.get_or_create(
                slug=DEMO_TENANT_SLUG,
                defaults={"name": DEMO_TENANT_NAME},
            )
            if tenant.name != DEMO_TENANT_NAME:
                raise CommandError(
                    "The reserved demo slug is already used by a non-demo store; no data was changed."
                )
            if tenant.status != Tenant.Status.ACTIVE:
                raise CommandError("The demo tenant is inactive; activate it before reseeding.")

            user = self._get_owner(email, tenant)
            membership, _ = Membership.objects.get_or_create(
                tenant=tenant,
                user=user,
                defaults={"role": Membership.Role.OWNER, "is_active": True},
            )
            if membership.role != Membership.Role.OWNER or not membership.is_active:
                raise CommandError("The demo owner membership must be active and have owner role.")

            branches = []
            for item in BRANCHES:
                branch, _ = Branch.objects.for_tenant(tenant.id).get_or_create(
                    code=item["code"],
                    defaults={
                        "tenant": tenant,
                        "name": item["name"],
                        "state_code": state_code,
                    },
                )
                if branch.name != item["name"] or not branch.is_active:
                    raise CommandError(
                        f"Demo branch {item['code']} conflicts with existing data."
                    )
                if branch.state_code and branch.state_code != state_code:
                    raise CommandError(
                        f"Branch {branch.code} has a different GST state code; no data changed."
                    )
                if not branch.state_code:
                    branch.state_code = state_code
                    branch.save(update_fields=["state_code", "updated_at"])
                access, _ = BranchAccess.objects.get_or_create(
                    membership=membership, branch=branch
                )
                if not access.is_active:
                    raise CommandError(f"Owner access to branch {branch.code} is inactive.")
                branches.append(branch)

            supplier, _ = Supplier.objects.for_tenant(tenant.id).get_or_create(
                name="Demo Wholesale Supplier",
                defaults={
                    "tenant": tenant,
                    "phone": "9000000001",
                    "email": "supplier@retailo-demo.local",
                    "address": "Demo Market, Mumbai, Maharashtra",
                },
            )

            products = []
            expected_fields = (
                "name", "unit", "hsn_code", "gst_rate", "selling_price", "purchase_price"
            )
            for item in PRODUCTS:
                product, _ = Product.objects.for_tenant(tenant.id).get_or_create(
                    sku=item["sku"],
                    defaults={"tenant": tenant, **item},
                )
                if any(getattr(product, field) != item[field] for field in expected_fields):
                    raise CommandError(
                        f"Demo SKU {product.sku} conflicts with existing product data."
                    )
                products.append(product)

            new_movements = 0
            for branch in branches:
                for product in products:
                    key = f"demo-opening-{branch.code}-{product.sku}"[:128]
                    movement = StockMovement.objects.for_tenant(tenant.id).filter(
                        idempotency_key=key
                    ).first()
                    balance, balance_created = (
                        InventoryBalance.objects.for_tenant(tenant.id).get_or_create(
                            branch=branch,
                            product=product,
                            defaults={
                                "tenant": tenant,
                                "quantity_on_hand": Decimal("0.000"),
                            },
                        )
                    )
                    if movement:
                        if (
                            movement.branch_id != branch.id
                            or movement.product_id != product.id
                            or movement.reason != StockMovement.Reason.OPENING
                            or movement.quantity_delta != OPENING_QUANTITY
                            or balance_created
                        ):
                            raise CommandError(
                                f"Opening stock data conflicts for {branch.code}/{product.sku}."
                            )
                        continue
                    if not balance_created and balance.quantity_on_hand != Decimal("0.000"):
                        raise CommandError(
                            f"A non-zero balance exists without the demo opening movement for "
                            f"{branch.code}/{product.sku}; no stock was changed."
                        )

                    balance.quantity_on_hand += OPENING_QUANTITY
                    balance.save(update_fields=["quantity_on_hand", "updated_at"])
                    StockMovement.objects.create(
                        tenant=tenant,
                        branch=branch,
                        product=product,
                        quantity_delta=OPENING_QUANTITY,
                        reason=StockMovement.Reason.OPENING,
                        reference="RETAILO-DEMO-OPENING",
                        idempotency_key=key,
                        note="Demo opening stock seeded by seed_demo.",
                        created_by=user,
                    )
                    new_movements += 1

        self.stdout.write(self.style.SUCCESS("Retailo demo data is ready."))
        self.stdout.write(f"Store: {tenant.name} ({tenant.slug})")
        self.stdout.write(f"Owner login: {email}")
        self.stdout.write(f"Branches: {len(branches)} | Products: {len(products)}")
        self.stdout.write(f"Supplier: {supplier.name}")
        self.stdout.write(f"New opening stock movements: {new_movements}")
        self.stdout.write(
            "GSTIN is intentionally blank; configure a valid branch GSTIN before invoicing."
        )
        if created:
            self.stdout.write("Created a dedicated demo tenant; existing stores were not modified.")

    def _get_owner(self, email, tenant):
        user_model = get_user_model()
        user = user_model.objects.filter(email__iexact=email).order_by("pk").first()
        if user:
            if user.email.strip().lower() != email or not user.is_active:
                raise CommandError("The existing email account cannot be used as demo owner.")
            membership = Membership.objects.filter(tenant=tenant, user=user).first()
            if membership is None:
                raise CommandError(
                    "That email already belongs to a user outside the demo store; "
                    "choose another --email."
                )
            if Membership.objects.filter(
                user=user, is_active=True, tenant__status=Tenant.Status.ACTIVE
            ).exclude(tenant=tenant).exists():
                raise CommandError(
                    "The account belongs to another active store; use a dedicated demo email."
                )
            return user

        password = os.environ.get("RETAILO_DEMO_PASSWORD", "")
        if not password:
            password = getpass.getpass("Set demo owner password (minimum 12 characters): ")
            confirmation = getpass.getpass("Confirm demo owner password: ")
            if password != confirmation:
                raise CommandError("Passwords do not match; no demo data was created.")
        if len(password) < 12:
            raise CommandError("RETAILO_DEMO_PASSWORD must be at least 12 characters.")
        return user_model.objects.create_user(
            **{user_model.USERNAME_FIELD: email},
            email=email,
            password=password,
        )
