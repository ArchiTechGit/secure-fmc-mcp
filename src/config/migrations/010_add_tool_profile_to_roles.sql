-- Migration 010: Add tool_profile_id to roles for role-level tool scoping
-- Version: 010
-- Date: 2026-04-18
-- Description: Extends the roles table with an optional tool profile FK so that
--              administrators can assign a default tool profile at the role level.
--              User-level profiles (from migration 006) continue to take priority
--              over role-level profiles when both are set.

-- ============================================================================
-- SCHEMA CHANGE: Add tool_profile_id column to roles
-- ============================================================================

ALTER TABLE roles
    ADD COLUMN IF NOT EXISTS tool_profile_id INTEGER
        REFERENCES tool_profiles(id) ON DELETE SET NULL;

-- Index for FK lookups and profile-based role queries
CREATE INDEX IF NOT EXISTS idx_roles_tool_profile_id ON roles(tool_profile_id);

COMMENT ON COLUMN roles.tool_profile_id IS
    'Optional tool profile for role-level tool scoping. When set, users with this role get these tools unless overridden by user-level profile.';

-- ============================================================================
-- SEED ADDITIONAL DEFAULT TOOL PROFILES
-- "Full Access" already exists from migration 006 - skip it.
-- Operations are populated from api_endpoints using FMC path-based filtering:
--   /api/fmc_config/v1/domain/{domainUUID}/object/   -> Object Management
--   /api/fmc_config/v1/domain/{domainUUID}/policy/   -> Policy Management
--   /api/fmc_config/v1/domain/{domainUUID}/devices/  -> Device Management
--   /api/fmc_config/v1/domain/{domainUUID}/troubleshoot/ -> Troubleshooting
-- ============================================================================

INSERT INTO tool_profiles (name, description, max_tools, is_active, created_at, updated_at)
VALUES
    (
        'Full Access',
        'All available operations (no filtering)',
        0,
        TRUE, NOW(), NOW()
    ),
    (
        'Read-Only Analyst',
        'All FMC GET operations — read-only access across objects, policies, devices, and deployment',
        668,
        TRUE, NOW(), NOW()
    ),
    (
        'Device Operator',
        'Read-write access to FMC device and chassis level operations',
        270,
        TRUE, NOW(), NOW()
    ),
    (
        'Policy Administrator',
        'Read-write access to FMC policy and object operations',
        836,
        TRUE, NOW(), NOW()
    ),
    (
        'Troubleshooting Only',
        'Packet capture, packet tracer, health monitoring, and deployment status checks',
        16,
        TRUE, NOW(), NOW()
    )
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- POPULATE tool_profile_operations FOR EACH PROFILE
-- Operation names follow the format: api_name || '_' || operation_id
-- which matches the fmc_{operationId} convention used throughout the server.
-- ============================================================================

-- "Read-Only Analyst": all GET operations across the entire FMC API
INSERT INTO tool_profile_operations (profile_id, operation_name, created_at)
SELECT
    (SELECT id FROM tool_profiles WHERE name = 'Read-Only Analyst'),
    api_name || '_' || operation_id,
    NOW()
FROM api_endpoints
WHERE api_name = 'fmc'
  AND http_method = 'GET'
ON CONFLICT DO NOTHING;

-- "Device Operator": all methods for device and chassis paths
INSERT INTO tool_profile_operations (profile_id, operation_name, created_at)
SELECT
    (SELECT id FROM tool_profiles WHERE name = 'Device Operator'),
    api_name || '_' || operation_id,
    NOW()
FROM api_endpoints
WHERE api_name = 'fmc'
  AND (
    path LIKE '%/devices/%'
    OR path LIKE '%/chassis/%'
  )
ON CONFLICT DO NOTHING;

-- "Policy Administrator": all methods for policy and object paths
INSERT INTO tool_profile_operations (profile_id, operation_name, created_at)
SELECT
    (SELECT id FROM tool_profiles WHERE name = 'Policy Administrator'),
    api_name || '_' || operation_id,
    NOW()
FROM api_endpoints
WHERE api_name = 'fmc'
  AND (
    path LIKE '%/policy/%'
    OR path LIKE '%/object/%'
  )
ON CONFLICT DO NOTHING;

-- "Troubleshooting Only": GET operations for troubleshoot, health, and deployment status
INSERT INTO tool_profile_operations (profile_id, operation_name, created_at)
SELECT
    (SELECT id FROM tool_profiles WHERE name = 'Troubleshooting Only'),
    api_name || '_' || operation_id,
    NOW()
FROM api_endpoints
WHERE api_name = 'fmc'
  AND http_method = 'GET'
  AND (
    path LIKE '%/troubleshoot/%'
    OR path LIKE '%/health/%'
    OR path LIKE '%/deployment/%'
  )
ON CONFLICT DO NOTHING;

-- ============================================================================
-- ASSIGN DEFAULT PROFILES TO SYSTEM ROLES
-- ============================================================================

-- Administrator gets full unrestricted access
UPDATE roles
SET tool_profile_id = (SELECT id FROM tool_profiles WHERE name = 'Full Access')
WHERE name = 'Administrator'
  AND is_system_role = TRUE;

-- Operator/Network Operator role maps to Full Access (Device Operator is a scoped subset)
UPDATE roles
SET tool_profile_id = (SELECT id FROM tool_profiles WHERE name = 'Full Access')
WHERE name IN ('Operator', 'Network Operator')
  AND is_system_role = TRUE;

-- Viewer role maps to the Read-Only Analyst tool profile
UPDATE roles
SET tool_profile_id = (SELECT id FROM tool_profiles WHERE name = 'Read-Only Analyst')
WHERE name IN ('Viewer', 'Read-Only User')
  AND is_system_role = TRUE;
