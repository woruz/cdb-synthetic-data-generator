-- Generated seeder (deterministic, FK-safe order)

INSERT INTO "customers" ("id", "name", "email", "customer_type") VALUES (1, 'name_116740xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'email_7', 'premium');
INSERT INTO "customers" ("id", "name", "email", "customer_type") VALUES (2, 'name_234054xxxxxxxxxxxxxxxxxxxxx', 'email_772247xxxxxxxxxxxxxxxxxxxxxxxx', 'regular');
INSERT INTO "customers" ("id", "name", "email", "customer_type") VALUES (3, 'name_776647xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'email_571859xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'regular');
INSERT INTO "customers" ("id", "name", "email", "customer_type") VALUES (4, 'name_442418xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'email_312', 'regular');

INSERT INTO "orders" ("id", "total", "status") VALUES (1, -56272405.03, 'cancelled');
INSERT INTO "orders" ("id", "total", "status") VALUES (2, 20403745.81, 'cancelled');
INSERT INTO "orders" ("id", "total", "status") VALUES (3, -60232469.86, 'cancelled');
INSERT INTO "orders" ("id", "total", "status") VALUES (4, -16096035.81, 'delivered');

INSERT INTO "payments" ("id", "amount", "payment_status") VALUES (1, 17853136.77, 'unpaid');
INSERT INTO "payments" ("id", "amount", "payment_status") VALUES (2, 51761473.42, 'unpaid');
INSERT INTO "payments" ("id", "amount", "payment_status") VALUES (3, 39627878.99, 'paid');
INSERT INTO "payments" ("id", "amount", "payment_status") VALUES (4, -44425731.66, 'unpaid');
