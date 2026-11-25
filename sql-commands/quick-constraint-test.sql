USE smart_office;
INSERT INTO department(dept_name) VALUES ('Engineering');
INSERT INTO employee(name,email,dept_id) VALUES ('Test','t@x.com',1);

-- should FAIL: duplicate email
INSERT INTO employee(name,email,dept_id) VALUES ('Dup','t@x.com',1);
-- should FAIL: department 99 does not exist
INSERT INTO employee(name,email,dept_id) VALUES ('Bad','b@x.com',99);