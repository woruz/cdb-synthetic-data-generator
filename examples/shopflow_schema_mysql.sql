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
