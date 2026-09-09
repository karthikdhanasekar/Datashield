-- Fix ENUM types in the database
-- Run this to convert VARCHAR columns to proper ENUM types

BEGIN;

-- Fix findings.severity
ALTER TABLE findings ALTER COLUMN severity DROP DEFAULT;
ALTER TABLE findings ALTER COLUMN severity TYPE severitylevel USING UPPER(severity)::severitylevel;
ALTER TABLE findings ALTER COLUMN severity SET DEFAULT 'LOW'::severitylevel;

-- Fix findings.finding_type  
ALTER TABLE findings ALTER COLUMN finding_type DROP DEFAULT;
ALTER TABLE findings ALTER COLUMN finding_type TYPE findingtype USING finding_type::findingtype;

-- Fix scan_requests.status
ALTER TABLE scan_requests ALTER COLUMN status DROP DEFAULT;
ALTER TABLE scan_requests ALTER COLUMN status TYPE scanstatus USING status::scanstatus;
ALTER TABLE scan_requests ALTER COLUMN status SET DEFAULT 'PENDING'::scanstatus;

-- Fix takedown_requests.status
ALTER TABLE takedown_requests ALTER COLUMN status DROP DEFAULT;
ALTER TABLE takedown_requests ALTER COLUMN status TYPE takedownstatus USING status::takedownstatus;
ALTER TABLE takedown_requests ALTER COLUMN status SET DEFAULT 'PENDING'::takedownstatus;

-- Fix users.role
ALTER TABLE users ALTER COLUMN role DROP DEFAULT;
ALTER TABLE users ALTER COLUMN role TYPE userrole USING UPPER(role)::userrole;
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'INDIVIDUAL'::userrole;

-- Fix users.status
ALTER TABLE users ALTER COLUMN status DROP DEFAULT;
ALTER TABLE users ALTER COLUMN status TYPE userstatus USING UPPER(status)::userstatus;
ALTER TABLE users ALTER COLUMN status SET DEFAULT 'PENDING_VERIFICATION'::userstatus;

COMMIT;
