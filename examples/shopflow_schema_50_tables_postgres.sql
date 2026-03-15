CREATE TYPE tenant_posture_t AS ENUM ('active','suspended','closed');
CREATE TYPE store_status_t AS ENUM ('active','maintenance','disabled');
CREATE TYPE order_status_t AS ENUM ('draft','pending','confirmed','packed','shipped','delivered','returned','cancelled');
CREATE TYPE payment_status_t AS ENUM ('unpaid','authorized','captured','refunded','chargeback');
CREATE TYPE channel_t AS ENUM ('email','sms','push');
CREATE TYPE priority_t AS ENUM ('low','medium','high');
CREATE TYPE aux_status_t AS ENUM ('open','closed');

CREATE TABLE tenants (
  id SERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  posture tenant_posture_t NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE stores (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(120) NOT NULL,
  domain VARCHAR(255) NOT NULL UNIQUE,
  status store_status_t NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  email VARCHAR(255) NOT NULL UNIQUE,
  full_name VARCHAR(120) NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  store_id INT NOT NULL REFERENCES stores(id),
  customer_id INT NOT NULL REFERENCES customers(id),
  status order_status_t NOT NULL,
  total NUMERIC(10,2) NOT NULL,
  placed_at TIMESTAMP NOT NULL
);

CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  amount NUMERIC(10,2) NOT NULL,
  payment_status payment_status_t NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE aux_table_01 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_02 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  channel channel_t NOT NULL
);

CREATE TABLE aux_table_03 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_04 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  priority priority_t NOT NULL
);

CREATE TABLE aux_table_05 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_06 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  status aux_status_t NOT NULL
);

CREATE TABLE aux_table_07 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_08 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  channel channel_t NOT NULL
);

CREATE TABLE aux_table_09 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_10 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  priority priority_t NOT NULL
);

CREATE TABLE aux_table_11 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_12 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  status aux_status_t NOT NULL
);

CREATE TABLE aux_table_13 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_14 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  channel channel_t NOT NULL
);

CREATE TABLE aux_table_15 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_16 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  priority priority_t NOT NULL
);

CREATE TABLE aux_table_17 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_18 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  status aux_status_t NOT NULL
);

CREATE TABLE aux_table_19 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_20 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  channel channel_t NOT NULL
);

CREATE TABLE aux_table_21 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_22 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  priority priority_t NOT NULL
);

CREATE TABLE aux_table_23 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_24 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  status aux_status_t NOT NULL
);

CREATE TABLE aux_table_25 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_26 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  channel channel_t NOT NULL
);

CREATE TABLE aux_table_27 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_28 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  priority priority_t NOT NULL
);

CREATE TABLE aux_table_29 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_30 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  status aux_status_t NOT NULL
);

CREATE TABLE aux_table_31 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_32 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  channel channel_t NOT NULL
);

CREATE TABLE aux_table_33 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_34 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  priority priority_t NOT NULL
);

CREATE TABLE aux_table_35 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_36 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  status aux_status_t NOT NULL
);

CREATE TABLE aux_table_37 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_38 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  channel channel_t NOT NULL
);

CREATE TABLE aux_table_39 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_40 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  priority priority_t NOT NULL
);

CREATE TABLE aux_table_41 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_42 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
  status aux_status_t NOT NULL
);

CREATE TABLE aux_table_43 (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES tenants(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);

CREATE TABLE aux_table_44 (
  id SERIAL PRIMARY KEY,
  customer_id INT NOT NULL REFERENCES customers(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL,
   channel channel_t NOT NULL
);

CREATE TABLE aux_table_45 (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES orders(id),
  name VARCHAR(80) NOT NULL,
  code VARCHAR(32) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
  
  
);
