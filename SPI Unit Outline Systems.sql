-- =====================================================================
-- SPI Unit Outline System — database schema
--
-- Run this ONCE to build the database, then fill in the DB_* variables
-- in your .env file so the app can connect to it.
--
-- Fixes applied to the original version of this file (each one is
-- marked FIXED below so you can see what changed and why):
--   1. DROP TABLE on a table that doesn't exist yet -> DROP IF EXISTS
--   2. "SpiUnitOUtlines" typo in the USE statement
--   3. StaffCourseAccess had a FOREIGN KEY on a course_id column that
--      was never declared -> the CREATE TABLE failed outright
--   4. EmailLogs had UnitOutlines' columns pasted into it, which don't
--      match what retrieve_database.py reads/writes
--   5. "emial_log_id" typo
--   6. Table names lowercased to match the Python. MySQL on Windows
--      treats UnitOutlines and unit_outlines as the same table, but on
--      Mac/Linux they're different tables — lowercase works on all
--      three, CamelCase only works on Windows.
--   7. Removed the SELECT * after every CREATE TABLE — they only
--      printed empty tables and made real errors harder to spot.
-- =====================================================================

DROP DATABASE IF EXISTS SpiUnitOutlines;
CREATE DATABASE SpiUnitOutlines;
USE SpiUnitOutlines;                        -- FIXED (2): was "SpiUnitOUtlines"


-- ---------------------------------------------------------------------
-- User roles
--
-- NOTE: this table isn't actually read by the app. Identity and roles
-- come from Azure AD (see auth/login.py), not from here. It's kept
-- because it documents who's who, but nothing queries it — don't rely
-- on it for permissions.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS user_roles;            -- FIXED (1): plain DROP failed on a fresh database
CREATE TABLE user_roles (
    user_name VARCHAR(100),
    user_role INT
);

INSERT INTO user_roles VALUES
    ('Anthony Kadi', 0),
    ('Imran Afridi', 1),
    ('Muhammad Kashif', 1),
    ('Hritika Adhikari', 1);


-- ---------------------------------------------------------------------
-- Courses — the course list on the dashboard.
-- Used by dashboard.py (GET/POST/PUT/DELETE /dashboard/api/courses).
--
-- Created BEFORE staff_course_access, because that table has a foreign
-- key pointing at this one — MySQL needs the target to already exist.
-- ---------------------------------------------------------------------
CREATE TABLE courses (
    course_id   INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(10) UNIQUE,
    name        VARCHAR(150),
    semester    VARCHAR(50),
    start_date  DATE,
    description VARCHAR(1000)
);


-- ---------------------------------------------------------------------
-- Staff course access — which staff member can edit which course.
--
-- This is what decides whether a non-admin is allowed to save a unit
-- outline (see _may_edit() in editing/routes.py). A staff member with
-- no rows here can't save anything, so remember to add a row per person
-- per course they own.
-- ---------------------------------------------------------------------
CREATE TABLE staff_course_access (
    staff_course_access_id INT AUTO_INCREMENT PRIMARY KEY,
    staff_email            VARCHAR(255),
    course_id              INT,             -- FIXED (3): was missing entirely, so the FK below failed
    FOREIGN KEY (course_id) REFERENCES courses(course_id)
);


-- ---------------------------------------------------------------------
-- Unit outlines — THE table the "Save Outline Changes" button fills.
--
-- One row per unit. `content` holds the whole outline as a JSON object
-- of the form's field ids, e.g.
--     {"unit_code": "ICT101", "title": "...", "lo1": "...", ...}
-- Each save replaces `content` and bumps `version` by 1.
-- Written by save_doc() in shared/retrieve_database.py.
-- ---------------------------------------------------------------------
CREATE TABLE unit_outlines (
    unit_outline_id INT AUTO_INCREMENT PRIMARY KEY,
    unit_code       VARCHAR(10),
    content         TEXT,
    last_edited_by  VARCHAR(255),
    last_edited_at  DATETIME,
    version         INT
);


-- ---------------------------------------------------------------------
-- History log — one row per save: who, when, which version.
--
-- NOTE ON DELETING OUTLINES: the foreign key below has no ON DELETE
-- rule, which means an outline that has history rows CANNOT be deleted
-- (MySQL blocks it), and a history row can't be added for an outline
-- that's already gone. That's why DeleteDoc in editing/editing.py is
-- still unwired. If you want deletion to work, pick one:
--
--   ON DELETE CASCADE   -- deleting an outline wipes its history too
--                       -- (simple, but you lose the audit trail)
--   ON DELETE SET NULL  -- history survives with a NULL outline id
--                       -- (keeps the audit trail; unit_outline_id
--                       --  must stay nullable, which it is)
--   soft delete         -- add a `deleted` flag to unit_outlines and
--                       -- never actually DELETE the row (recommended
--                       --  for a system built around approvals)
--
-- Left as-is here so the decision stays yours rather than being made
-- silently by this file.
-- ---------------------------------------------------------------------
CREATE TABLE history_log (
    history_log_id  INT AUTO_INCREMENT PRIMARY KEY,
    unit_outline_id INT,
    action          VARCHAR(20),            -- 'saved' or 'deleted'
    editor_email    VARCHAR(255),
    edited_at       DATETIME,
    version         INT,
    FOREIGN KEY (unit_outline_id) REFERENCES unit_outlines(unit_outline_id)
);


-- ---------------------------------------------------------------------
-- Approvals — the "Request a Change" workflow.
-- Written by create_approval(), read by get_approval(), updated when
-- the coordinator clicks Approve/Reject in their email.
-- ---------------------------------------------------------------------
CREATE TABLE approvals (
    approval_id       INT AUTO_INCREMENT PRIMARY KEY,
    token             VARCHAR(36) UNIQUE,
    unit_code         VARCHAR(10),
    coordinator_email VARCHAR(255),
    status            VARCHAR(20),          -- 'Pending' / 'Approved' / 'Rejected'
    reason            VARCHAR(500) NULL,
    created_at        DATETIME
);


-- ---------------------------------------------------------------------
-- Email logs — a record of every approval email sent.
--
-- FIXED (4): the original version of this table had UnitOutlines'
-- columns (unit_code / content / last_edited_by / last_edited_at /
-- version) pasted into it by mistake. Those aren't the columns
-- retrieve_database.py reads and writes, so every email log operation
-- would have failed with "Unknown column". These are the right ones.
-- ---------------------------------------------------------------------
CREATE TABLE email_logs (
    email_log_id     INT AUTO_INCREMENT PRIMARY KEY,   -- FIXED (5): was "emial_log_id"
    recipient        VARCHAR(255),
    subject          VARCHAR(255),
    status           VARCHAR(50),           -- did the send itself succeed
    token            VARCHAR(36),           -- links back to approvals.token
    action_status    VARCHAR(20),           -- 'Pending' / 'Approved' / 'Rejected'
    rejection_reason VARCHAR(500) NULL,
    sent_at          DATETIME
);


-- =====================================================================
-- Sample data — delete this section once you have real courses.
--
-- Two courses, and edit access for one of them, so you can test that
-- a non-admin can save the unit they own and gets refused on the one
-- they don't. Replace the email with a real staff address (it must
-- match the Azure AD account exactly).
-- =====================================================================
INSERT INTO courses (code, name, semester, start_date, description) VALUES
    ('ICT101', 'Introduction to Computing', 'Semester 1', '2026-02-23', 'Foundations of computing.'),
    ('ICT202', 'Cyber Security Basics',     'Semester 2', '2026-07-20', 'Security fundamentals.');

INSERT INTO staff_course_access (staff_email, course_id) VALUES
    ('dev-unitcoord@spi.edu.au', 1);


-- =====================================================================
-- Check it worked — should list 7 tables and 2 courses.
-- =====================================================================
SHOW TABLES;
SELECT * FROM courses;
