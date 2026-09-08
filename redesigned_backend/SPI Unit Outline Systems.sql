CREATE DATABASE SpiUnitOutlines;
USE SpiUnitOUtlines;
DROP TABLE UserRoles;
CREATE TABLE UserRoles (
user_name VARCHAR(100),
user_role INT
);
INSERT INTO UserRoles VALUES
('Anthony Kadi', 0),
('Imran Afridi', 1),
('Muhammad Kashif', 1),
('Hritika Adhikari', 1);
SELECT * FROM UserRoles;
CREATE TABLE Approvals (
approval_id INT AUTO_INCREMENT PRIMARY KEY,
token VARCHAR(36) UNIQUE,
unit_code VARCHAR(10),
coordinator_email VARCHAR(255),
status VARCHAR(20),
reason VARCHAR(500) NULL,
created_at DATETIME
);
SELECT * FROM Approvals;
CREATE TABLE EmailLogs (
emial_log_id INT AUTO_INCREMENT PRIMARY KEY,
unit_code VARCHAR(10),
content TEXT,
last_edited_by VARCHAR(255),
last_edited_at DATETIME,
version INT
);
SELECT * FROM EmailLogs;
CREATE TABLE UnitOutlines (
unit_outline_id INT AUTO_INCREMENT PRIMARY KEY,
unit_code VARCHAR(10),
content TEXT,
last_edited_by VARCHAR(255),
last_edited_at DATETIME,
version INT
);
SELECT * FROM UnitOutlines;
CREATE TABLE HistoryLog (
history_log_id INT AUTO_INCREMENT PRIMARY KEY,
unit_outline_id INT,
action VARCHAR(20),
editor_email VARCHAR(255),
edited_at DATETIME,
version INT,
FOREIGN KEY (unit_outline_id) REFERENCES unit_outlines(unit_outline_id)
);
SELECT * FROM HistoryLog;
CREATE TABLE Courses (
course_id INT AUTO_INCREMENT PRIMARY KEY,
code VARCHAR(10) UNIQUE,
name VARCHAR(150),
semester VARCHAR(50),
start_date DATE,
description VARCHAR(1000)
);
SELECT * FROM Courses;
CREATE TABLE StaffCourseAccess (
staff_course_access_id INT AUTO_INCREMENT PRIMARY KEY,
staff_email VARCHAR(255),
FOREIGN KEY (course_id) REFERENCES courses(course_id)
);
SELECT * FROM StaffCourseAccess;