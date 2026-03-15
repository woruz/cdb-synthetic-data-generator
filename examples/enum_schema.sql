CREATE TYPE customer_type_t AS ENUM ('regular','premium');
CREATE TYPE order_status_t AS ENUM ('pending','processing','shipped','delivered','cancelled');
CREATE TYPE payment_status_t AS ENUM ('unpaid','paid','refunded');

CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(255) NOT NULL,
  customer_type customer_type_t NOT NULL
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  total NUMERIC(10,2) NOT NULL,
  status order_status_t NOT NULL
);

CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  amount NUMERIC(10,2) NOT NULL,
  payment_status payment_status_t NOT NULL
);
