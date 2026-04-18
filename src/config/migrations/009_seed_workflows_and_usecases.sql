-- Migration 009: Seed built-in FMC workflows and use cases
-- Version: 009
-- Date: 2026-04-18
-- Description: Seeds 6 practical FMC workflows with steps and 5 use cases
--              covering common firewall management and operations tasks.

-- ============================================================================
-- WORKFLOWS
-- ============================================================================

INSERT INTO workflows (name, display_name, description, problem_statement, use_case_tags, is_active, priority, created_at, updated_at)
VALUES
    (
        'deploy_config_changes',
        'Deploy Configuration Changes',
        'Identify devices with pending changes, review recent deployment history, push changes, and confirm successful deployment.',
        'Configuration changes have been made and need to be deployed to one or more FMC-managed devices.',
        '["change-management", "deployment", "operations"]',
        TRUE, 100, NOW(), NOW()
    ),
    (
        'access_policy_review',
        'Access Control Policy Review',
        'Audit access control policies and rules, verify referenced network objects and security zones, and confirm IPS assignments.',
        'Review access control policies for correctness, coverage, and security posture.',
        '["policy", "security", "audit", "access-control"]',
        TRUE, 95, NOW(), NOW()
    ),
    (
        'device_health_check',
        'Managed Device Health Check',
        'List all FMC-managed devices, check for pending changes, review HA pair state, and confirm health monitoring coverage.',
        'Verify the health and operational status of all FMC-managed firewall devices.',
        '["device-management", "health", "monitoring", "ha"]',
        TRUE, 90, NOW(), NOW()
    ),
    (
        'network_object_audit',
        'Network Object Audit',
        'Inventory all network, host, group, port, URL, and FQDN objects to identify gaps, duplicates, or stale entries.',
        'Audit the FMC object library to ensure objects are current and consistently named.',
        '["object-management", "audit", "compliance"]',
        TRUE, 85, NOW(), NOW()
    ),
    (
        'nat_policy_review',
        'NAT Policy Review',
        'List all NAT policies, verify device assignments, and review referenced network objects for accuracy.',
        'Review NAT policies for correctness and ensure they are assigned to the appropriate devices.',
        '["policy", "nat", "audit"]',
        TRUE, 80, NOW(), NOW()
    ),
    (
        'intrusion_prevention_audit',
        'Intrusion Prevention Audit',
        'List all intrusion policies, identify which access policies use IPS, and confirm IPS-enabled policies are deployed to devices.',
        'Verify that intrusion prevention is correctly configured and actively protecting managed devices.',
        '["security", "ips", "intrusion", "audit"]',
        TRUE, 75, NOW(), NOW()
    )
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- WORKFLOW STEPS
-- ============================================================================

-- 1. Deploy Configuration Changes
INSERT INTO workflow_steps (workflow_id, step_order, operation_name, description, expected_output, optional, created_at)
SELECT w.id, v.step_order, v.operation_name, v.description, v.expected_output, v.optional, NOW()
FROM workflows w
CROSS JOIN (VALUES
    (1, 'fmc_getAllDeployableDevices',  'List devices with pending configuration changes not yet deployed', 'Device list with pending change counts and last-modified timestamps', FALSE),
    (2, 'fmc_getAllDeploymentRequests', 'Review recent deployment history to understand what was last pushed', 'Recent deployments: device, status, timestamp, and initiated-by', FALSE),
    (3, 'fmc_createDeploymentRequest',  'Deploy pending changes to selected devices', 'Deployment job ID and initial status', FALSE),
    (4, 'fmc_getJobStatus',            'Poll deployment job until complete and confirm success or failure', 'Final job status: completed, failed, or in-progress with error detail', FALSE)
) AS v(step_order, operation_name, description, expected_output, optional)
WHERE w.name = 'deploy_config_changes'
AND NOT EXISTS (
    SELECT 1 FROM workflow_steps ws WHERE ws.workflow_id = w.id AND ws.step_order = v.step_order
);

-- 2. Access Control Policy Review
INSERT INTO workflow_steps (workflow_id, step_order, operation_name, description, expected_output, optional, created_at)
SELECT w.id, v.step_order, v.operation_name, v.description, v.expected_output, v.optional, NOW()
FROM workflows w
CROSS JOIN (VALUES
    (1, 'fmc_getAllAccessPolicies',     'List all access control policies and their default actions', 'Policy names, IDs, default actions, and description', FALSE),
    (2, 'fmc_getAllAccessRules',        'Retrieve the rules within a specific access control policy', 'Rule list: name, action, source/dest zones, networks, ports, IPS policy', FALSE),
    (3, 'fmc_getAllNetworkObjects',     'List network objects referenced by rules to verify they are current', 'Network object inventory: name, value, type, description', FALSE),
    (4, 'fmc_getAllSecurityZoneObjects','Verify security zones used in policy rules are correctly defined', 'Zone list with interface assignments and descriptions', FALSE),
    (5, 'fmc_getAllIntrusionPolicies',  'Check available intrusion policies and confirm assignments in access rules', 'IPS policy list with base policies and descriptions', TRUE)
) AS v(step_order, operation_name, description, expected_output, optional)
WHERE w.name = 'access_policy_review'
AND NOT EXISTS (
    SELECT 1 FROM workflow_steps ws WHERE ws.workflow_id = w.id AND ws.step_order = v.step_order
);

-- 3. Managed Device Health Check
INSERT INTO workflow_steps (workflow_id, step_order, operation_name, description, expected_output, optional, created_at)
SELECT w.id, v.step_order, v.operation_name, v.description, v.expected_output, v.optional, NOW()
FROM workflows w
CROSS JOIN (VALUES
    (1, 'fmc_getAllDevices',           'List all FMC-managed devices with registration status and software version', 'Device inventory: name, model, version, registration status, domain', FALSE),
    (2, 'fmc_getAllDeployableDevices', 'Identify devices with pending configuration changes', 'Devices with pending changes and number of changes awaiting deployment', FALSE),
    (3, 'fmc_getAllFTDHAPairs',        'Check HA pair state and failover health for redundant deployments', 'HA pair status: active/standby state, failover reason, last failover time', FALSE),
    (4, 'fmc_getAllHealthPolicies',    'Confirm health monitoring policies are configured and assigned to devices', 'Health policy list with test modules and alert thresholds', TRUE)
) AS v(step_order, operation_name, description, expected_output, optional)
WHERE w.name = 'device_health_check'
AND NOT EXISTS (
    SELECT 1 FROM workflow_steps ws WHERE ws.workflow_id = w.id AND ws.step_order = v.step_order
);

-- 4. Network Object Audit
INSERT INTO workflow_steps (workflow_id, step_order, operation_name, description, expected_output, optional, created_at)
SELECT w.id, v.step_order, v.operation_name, v.description, v.expected_output, v.optional, NOW()
FROM workflows w
CROSS JOIN (VALUES
    (1, 'fmc_getAllNetworkObjects',      'Inventory all host and network CIDR objects', 'Network object list: name, value, type, description, overridable', FALSE),
    (2, 'fmc_getAllHostGroupObjects',    'Review network group memberships for correctness', 'Group list with member objects and nested group references', FALSE),
    (3, 'fmc_getAllProtocolPortObjects', 'Audit port and protocol service objects', 'Port object list: name, protocol, port range, description', FALSE),
    (4, 'fmc_getAllURLObjects',          'Review URL objects used in access and SSL policies', 'URL object list: name, URL value, description', FALSE),
    (5, 'fmc_getAllFQDNObjects',         'Check FQDN objects for currency and DNS resolution', 'FQDN object list: name, FQDN value, DNS resolution setting', TRUE)
) AS v(step_order, operation_name, description, expected_output, optional)
WHERE w.name = 'network_object_audit'
AND NOT EXISTS (
    SELECT 1 FROM workflow_steps ws WHERE ws.workflow_id = w.id AND ws.step_order = v.step_order
);

-- 5. NAT Policy Review
INSERT INTO workflow_steps (workflow_id, step_order, operation_name, description, expected_output, optional, created_at)
SELECT w.id, v.step_order, v.operation_name, v.description, v.expected_output, v.optional, NOW()
FROM workflows w
CROSS JOIN (VALUES
    (1, 'fmc_getAllFTDNatPolicies', 'List all FTD NAT policies and their descriptions', 'NAT policy list: name, description, assigned devices', FALSE),
    (2, 'fmc_getAllDevices',        'Confirm which devices have NAT policies assigned', 'Device list with policy assignments and deployment status', FALSE),
    (3, 'fmc_getAllNetworkObjects', 'Review network objects used in NAT translated/original addresses', 'Network object inventory to validate NAT address references', TRUE)
) AS v(step_order, operation_name, description, expected_output, optional)
WHERE w.name = 'nat_policy_review'
AND NOT EXISTS (
    SELECT 1 FROM workflow_steps ws WHERE ws.workflow_id = w.id AND ws.step_order = v.step_order
);

-- 6. Intrusion Prevention Audit
INSERT INTO workflow_steps (workflow_id, step_order, operation_name, description, expected_output, optional, created_at)
SELECT w.id, v.step_order, v.operation_name, v.description, v.expected_output, v.optional, NOW()
FROM workflows w
CROSS JOIN (VALUES
    (1, 'fmc_getAllIntrusionPolicies', 'List all intrusion policies with their base policies and rule counts', 'IPS policy list: name, base policy, inspection mode, description', FALSE),
    (2, 'fmc_getAllAccessPolicies',    'Identify access control policies that reference an intrusion policy', 'Access policy list to cross-reference IPS assignments in rules', FALSE),
    (3, 'fmc_getAllDevices',           'Verify that IPS-enabled access policies are deployed to managed devices', 'Device list with currently deployed policy names', FALSE)
) AS v(step_order, operation_name, description, expected_output, optional)
WHERE w.name = 'intrusion_prevention_audit'
AND NOT EXISTS (
    SELECT 1 FROM workflow_steps ws WHERE ws.workflow_id = w.id AND ws.step_order = v.step_order
);

-- ============================================================================
-- USE CASES
-- ============================================================================

INSERT INTO use_cases (name, display_name, description, category, is_active, created_at, updated_at)
VALUES
    (
        'change_management',
        'Change Management',
        'Deploy and track configuration changes to FMC-managed devices with full pre/post deployment verification.',
        'operations',
        TRUE, NOW(), NOW()
    ),
    (
        'policy_review',
        'Policy Review',
        'Audit and validate access control and NAT policies, rules, and object references for correctness and security posture.',
        'security',
        TRUE, NOW(), NOW()
    ),
    (
        'device_operations',
        'Device Operations',
        'Monitor the health, status, and pending changes across all FMC-managed firewall devices.',
        'operations',
        TRUE, NOW(), NOW()
    ),
    (
        'object_management',
        'Object Management',
        'Audit the FMC object library — networks, groups, ports, URLs, and FQDNs — to maintain hygiene and consistency.',
        'compliance',
        TRUE, NOW(), NOW()
    ),
    (
        'security_hardening',
        'Security Hardening',
        'Review intrusion prevention policies and confirm IPS is correctly deployed and active across managed devices.',
        'security',
        TRUE, NOW(), NOW()
    )
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- USE CASE <-> WORKFLOW LINKS
-- ============================================================================

INSERT INTO use_case_workflows (use_case_id, workflow_id, created_at)
SELECT uc.id, w.id, NOW()
FROM use_cases uc, workflows w
WHERE (uc.name, w.name) IN (
    ('change_management',  'deploy_config_changes'),
    ('policy_review',      'access_policy_review'),
    ('policy_review',      'nat_policy_review'),
    ('device_operations',  'device_health_check'),
    ('device_operations',  'deploy_config_changes'),
    ('object_management',  'network_object_audit'),
    ('security_hardening', 'intrusion_prevention_audit'),
    ('security_hardening', 'access_policy_review')
)
ON CONFLICT (use_case_id, workflow_id) DO NOTHING;
