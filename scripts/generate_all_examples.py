#!/usr/bin/env python3
"""
Generate all example files: 200-page SRS PDF + schemas for Postgres, MySQL, SQL Server, MongoDB.

Run from project root:
  python scripts/generate_all_examples.py

Or with venv:
  .venv/bin/python scripts/generate_all_examples.py
"""

from __future__ import annotations

import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def generate_pdf() -> None:
    """Generate 200-page SRS PDF using the PDF generator module."""
    import sys
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from generate_example_pdf import main as pdf_main
    pdf_main()


def generate_postgres_50_tables() -> None:
    out = EXAMPLES_DIR / "shopflow_schema_50_tables_postgres.sql"
    enum_sql = """
CREATE TYPE tenant_posture_t AS ENUM ('active','suspended','closed');
CREATE TYPE store_status_t AS ENUM ('active','maintenance','disabled');
CREATE TYPE order_status_t AS ENUM ('draft','pending','confirmed','packed','shipped','delivered','returned','cancelled');
CREATE TYPE payment_status_t AS ENUM ('unpaid','authorized','captured','refunded','chargeback');
""".strip()
    base = [
        """
CREATE TABLE tenants (
  id SERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  posture tenant_posture_t NOT NULL,
  created_at TIMESTAMP NOT NULL
);
""".strip(),
        """
CREATE TABLE stores (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(120) NOT NULL,
  domain VARCHAR(255) NOT NULL UNIQUE,
  status store_status_t NOT NULL,
  created_at TIMESTAMP NOT NULL
);
""".strip(),
        """
CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  email VARCHAR(255) NOT NULL UNIQUE,
  full_name VARCHAR(120) NOT NULL,
  created_at TIMESTAMP NOT NULL
);
""".strip(),
        """
CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  store_id INT NOT NULL REFERENCES stores(id),
  customer_id INT NOT NULL REFERENCES customers(id),
  status order_status_t NOT NULL,
  total NUMERIC(10,2) NOT NULL,
  placed_at TIMESTAMP NOT NULL
);
""".strip(),
        """
CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  amount NUMERIC(10,2) NOT NULL,
  payment_status payment_status_t NOT NULL,
  created_at TIMESTAMP NOT NULL
);
""".strip(),
    ]
    tables = [enum_sql] + base
    for i in range(1, 46):
        if i % 3 == 0:
            parent, parent_fk = "orders", "order_id"
            check = "CHECK (status IN ('open','closed'))" if i % 2 == 0 else ""
        elif i % 3 == 1:
            parent, parent_fk = "tenants", "tenant_id"
            check = "CHECK (priority IN ('low','medium','high'))" if i % 2 == 0 else ""
        else:
            parent, parent_fk = "customers", "customer_id"
            check = "CHECK (channel IN ('email','sms','push'))" if i % 2 == 0 else ""
        tname = f"aux_table_{i:02d}"
        ddl = f"""
CREATE TABLE {tname} (
  id SERIAL PRIMARY KEY,
  {parent_fk} INT NOT NULL REFERENCES {parent}(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  {',' if check else ''}
  {check}
);
""".strip()
        tables.append(ddl)
    out.write_text("\n\n".join(tables) + "\n", encoding="utf-8")
    print(f"Wrote {out.name} ({len(tables) - 1} tables)")


def generate_mysql_schema() -> None:
    out = EXAMPLES_DIR / "shopflow_schema_mysql.sql"
    sql = """
CREATE TABLE tenants (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  posture ENUM('active','suspended','closed') NOT NULL
);

CREATE TABLE customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT NOT NULL,
  email VARCHAR(255) NOT NULL,
  full_name VARCHAR(120) NOT NULL,
  customer_type ENUM('regular','premium') NOT NULL,
  UNIQUE(email),
  FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  status ENUM('pending','paid','cancelled','refunded') NOT NULL,
  total DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);
"""
    out.write_text(sql.strip() + "\n", encoding="utf-8")
    print(f"Wrote {out.name}")


def generate_sqlserver_schema() -> None:
    out = EXAMPLES_DIR / "shopflow_schema_sqlserver.sql"
    sql = """
CREATE TABLE [dbo].[Tenants] (
  [Id] INT IDENTITY(1,1) PRIMARY KEY,
  [Name] NVARCHAR(120) NOT NULL,
  [Posture] NVARCHAR(20) NOT NULL
);

CREATE TABLE [dbo].[Orders] (
  [Id] INT IDENTITY(1,1) PRIMARY KEY,
  [TenantId] INT NOT NULL,
  [Status] NVARCHAR(20) NOT NULL,
  [Total] DECIMAL(10,2) NOT NULL,
  CONSTRAINT [FK_Orders_Tenants] FOREIGN KEY ([TenantId]) REFERENCES [dbo].[Tenants]([Id]),
  CONSTRAINT [CK_Orders_Status] CHECK ([Status] IN ('draft','pending','confirmed','cancelled'))
);
"""
    out.write_text(sql.strip() + "\n", encoding="utf-8")
    print(f"Wrote {out.name}")


def generate_mongo_schema() -> None:
    out = EXAMPLES_DIR / "shopflow_schema_mongo.json"
    schema = {
        "tenants": {
            "properties": {
                "tenant_id": {"type": "string"},
                "name": {"type": "string", "maxLength": 120},
                "posture": {"type": "string", "enum": ["active", "suspended", "closed"]},
                "created_at": {"type": "string"},
            },
            "required": ["tenant_id", "name", "posture"],
        },
        "orders": {
            "properties": {
                "order_id": {"type": "string"},
                "tenant_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["draft", "pending", "confirmed", "packed", "shipped", "delivered", "returned", "cancelled"],
                },
                "total": {"type": "number"},
            },
            "required": ["order_id", "tenant_id", "status", "total"],
        },
    }
    out.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {out.name}")


def generate_short_srs() -> None:
    out = EXAMPLES_DIR / "shopflow_srs_short.txt"
    text = """ShopFlow (Synthetic) SRS Summary

Entities:
- Tenant: posture enum [active, suspended, closed]
- Store: status enum [active, maintenance, disabled]
- Customer: email unique, full_name required
- Order: status enum [draft, pending, confirmed, packed, shipped, delivered, returned, cancelled]
- Payment: payment_status enum [unpaid, authorized, captured, refunded, chargeback]

Rules:
- Each store belongs to one tenant.
- Each customer belongs to one tenant.
- Each order belongs to one tenant, one store, and one customer.
- Each payment belongs to one order.
- All status enums must use allowed values only.
- totals/amount are NUMERIC(10,2) and must be within DB bounds.
"""
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out.name}")


def main() -> int:
    print("Generating examples in", EXAMPLES_DIR)
    generate_short_srs()
    generate_postgres_50_tables()
    generate_mysql_schema()
    generate_sqlserver_schema()
    generate_mongo_schema()
    try:
        generate_pdf()
    except Exception as e:
        print("PDF generation failed:", e)
        print("Install pypdf and run: python scripts/generate_example_pdf.py")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
