-- Generated seeder (deterministic, FK-safe order)

INSERT INTO "customers" ("id", "name", "email", "customer_type") VALUES (1, 'name_1825aaaaaaaaaaaa', 'email_4507hhhhhhhhhhhhhh', 'regular');
INSERT INTO "customers" ("id", "name", "email", "customer_type") VALUES (2, 'name_', 'email_8936cccccccccccc', 'premium');
INSERT INTO "customers" ("id", "name", "email", "customer_type") VALUES (3, 'na', 'ema', 'regular');

INSERT INTO "orders" ("id", "customer_id", "total", "status") VALUES (1, 3, 60201872.9, 'cancelled');
INSERT INTO "orders" ("id", "customer_id", "total", "status") VALUES (2, 1, 71601961.29, 'cancelled');
INSERT INTO "orders" ("id", "customer_id", "total", "status") VALUES (3, 2, 22044062.2, 'cancelled');

INSERT INTO "payments" ("id", "order_id", "amount", "payment_status") VALUES (1, 2, 80943045.66, 'unpaid');
INSERT INTO "payments" ("id", "order_id", "amount", "payment_status") VALUES (2, 1, 69813939.49, 'paid');
INSERT INTO "payments" ("id", "order_id", "amount", "payment_status") VALUES (3, 2, 15547949.98, 'paid');
