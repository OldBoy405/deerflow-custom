-- DeerFlow RBAC + ABAC authorization bootstrap script
-- Includes: schema, indexes, seed data, and 10 sample policies.
-- Usage:
--   psql "postgresql://user:pass@host:5432/dbname" -v ON_ERROR_STOP=1 -f docs/sql/authz_init.sql

begin;

-- ============================================
-- 0) Cleanup (optional but deterministic)
-- ============================================
drop table if exists authz_audit_logs;
drop table if exists policies;
drop table if exists resources;
drop table if exists user_roles;
drop table if exists roles;
drop table if exists users;
drop table if exists departments;

-- ============================================
-- 1) Core identity tables
-- ============================================
create table departments (
  id                bigserial primary key,
  dept_code         text not null unique,
  dept_name         text not null,
  parent_id         bigint references departments(id),
  status            text not null default 'active',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create table users (
  id                bigserial primary key,
  user_id           text not null unique, -- Maps JWT sub
  username          text not null,
  email             text,
  dept_id           bigint references departments(id),
  status            text not null default 'active',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create table roles (
  id                bigserial primary key,
  role_code         text not null unique, -- viewer/developer/admin...
  role_name         text not null,
  priority          int not null default 100,
  status            text not null default 'active',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create table user_roles (
  user_id           bigint not null references users(id) on delete cascade,
  role_id           bigint not null references roles(id) on delete cascade,
  expires_at        timestamptz,
  primary key (user_id, role_id)
);

-- ============================================
-- 2) Resource catalog
-- ============================================
create table resources (
  id                bigserial primary key,
  resource_type     text not null check (resource_type in ('TOOL', 'KB', 'MCP_TOOL')),
  namespace         text not null default '*',
  kb_id             text,
  resource_key      text not null unique,
  attributes        jsonb not null default '{}'::jsonb,
  status            text not null default 'active',
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- ============================================
-- 3) Policies (RBAC + ABAC)
-- ============================================
create table policies (
  id                bigserial primary key,
  policy_code       text not null unique,
  effect            text not null check (effect in ('ALLOW', 'DENY')),
  subject_type      text not null check (subject_type in ('USER', 'ROLE', 'DEPT', 'ALL')),
  subject_id        text not null, -- user_id / role_code / dept_code / *
  resource_type     text not null check (resource_type in ('TOOL', 'KB', 'MCP_TOOL', 'ALL')),
  namespace_pattern text not null default '*',
  resource_pattern  text not null default '*',
  action            text not null default '*', -- read/write/execute/search/admin/*
  condition_json    jsonb not null default '{}'::jsonb,
  priority          int not null default 1000, -- lower number = higher priority
  enabled           boolean not null default true,
  valid_from        timestamptz,
  valid_to          timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- ============================================
-- 4) Authorization audit logs
-- ============================================
create table authz_audit_logs (
  id                 bigserial primary key,
  request_id         text,
  user_id            text,
  dept_code          text,
  roles              text[],
  tool_name          text,
  action             text,
  resource_key       text,
  decision           text not null check (decision in ('ALLOW', 'DENY')),
  matched_policy_id  bigint,
  reason_code        text,
  reason_message     text,
  context            jsonb not null default '{}'::jsonb,
  created_at         timestamptz not null default now()
);

-- ============================================
-- 5) Indexes
-- ============================================
create index idx_users_user_id on users(user_id);
create index idx_users_dept_id on users(dept_id);

create index idx_roles_role_code on roles(role_code);
create index idx_user_roles_user on user_roles(user_id);
create index idx_user_roles_role on user_roles(role_id);

create index idx_resources_type_key on resources(resource_type, resource_key);
create index idx_resources_namespace_kb on resources(namespace, kb_id);

create index idx_policies_enabled_priority on policies(enabled, priority);
create index idx_policies_subject on policies(subject_type, subject_id);
create index idx_policies_resource on policies(resource_type, namespace_pattern, resource_pattern);
create index idx_policies_action on policies(action);
create index idx_policies_validity on policies(valid_from, valid_to);

create index idx_audit_created_at on authz_audit_logs(created_at desc);
create index idx_audit_user_id on authz_audit_logs(user_id);
create index idx_audit_decision on authz_audit_logs(decision);

-- ============================================
-- 6) Seed data: departments/users/roles/mappings
-- ============================================
insert into departments (dept_code, dept_name) values
('HQ', '总部'),
('FIN', '财务部'),
('RND', '研发部'),
('OPS', '运维部');

insert into users (user_id, username, email, dept_id)
select 'u_fin_001', 'Alice', 'alice@example.com', d.id from departments d where d.dept_code = 'FIN'
union all
select 'u_rnd_001', 'Bob', 'bob@example.com', d.id from departments d where d.dept_code = 'RND'
union all
select 'u_ops_001', 'Carol', 'carol@example.com', d.id from departments d where d.dept_code = 'OPS'
union all
select 'u_admin_001', 'Root', 'root@example.com', d.id from departments d where d.dept_code = 'HQ';

insert into roles (role_code, role_name, priority) values
('viewer', '只读角色', 300),
('developer', '研发角色', 200),
('ops', '运维角色', 200),
('admin', '管理员', 10),
('finance_editor', '财务知识库编辑', 150);

insert into user_roles (user_id, role_id)
select u.id, r.id
from users u
join roles r on r.role_code = 'finance_editor'
where u.user_id = 'u_fin_001';

insert into user_roles (user_id, role_id)
select u.id, r.id
from users u
join roles r on r.role_code = 'viewer'
where u.user_id in ('u_fin_001', 'u_rnd_001');

insert into user_roles (user_id, role_id)
select u.id, r.id
from users u
join roles r on r.role_code = 'developer'
where u.user_id = 'u_rnd_001';

insert into user_roles (user_id, role_id)
select u.id, r.id
from users u
join roles r on r.role_code = 'ops'
where u.user_id = 'u_ops_001';

insert into user_roles (user_id, role_id)
select u.id, r.id
from users u
join roles r on r.role_code = 'admin'
where u.user_id = 'u_admin_001';

-- ============================================
-- 7) Seed data: resources
-- ============================================
insert into resources (resource_type, namespace, kb_id, resource_key, attributes) values
('TOOL', '*', null, 'tool:read_file', '{}'::jsonb),
('TOOL', '*', null, 'tool:write_file', '{}'::jsonb),
('TOOL', '*', null, 'tool:str_replace', '{}'::jsonb),
('TOOL', '*', null, 'tool:bash', '{}'::jsonb),
('TOOL', '*', null, 'tool:web_search', '{}'::jsonb),
('TOOL', '*', null, 'tool:web_fetch', '{}'::jsonb),
('KB', 'corp.cn.finance', 'kb_invoice_001', 'kb:corp.cn.finance:kb_invoice_001', '{"classification":"internal"}'::jsonb),
('KB', 'corp.cn.rnd', 'kb_rag_guide_001', 'kb:corp.cn.rnd:kb_rag_guide_001', '{"classification":"internal"}'::jsonb),
('MCP_TOOL', 'notion', null, 'mcp:notion:query_database', '{"server_name":"notion"}'::jsonb),
('MCP_TOOL', 'github', null, 'mcp:github:create_issue', '{"server_name":"github"}'::jsonb);

-- ============================================
-- 8) 10 sample policies
-- ============================================
insert into policies (
  policy_code, effect, subject_type, subject_id, resource_type, namespace_pattern, resource_pattern, action, condition_json, priority, enabled
) values
-- 1) Global deny: viewer cannot use bash
('P001_DENY_VIEWER_BASH', 'DENY', 'ROLE', 'viewer', 'TOOL', '*', 'tool:bash', 'execute', '{}'::jsonb, 10, true),

-- 2) Global deny: block bash on subagent (ABAC)
('P002_DENY_SUBAGENT_BASH', 'DENY', 'ALL', '*', 'TOOL', '*', 'tool:bash', 'execute',
 '{"require_subagent": false}'::jsonb, 15, true),

-- 3) Allow: viewer can read files
('P003_ALLOW_VIEWER_READ_TOOLS', 'ALLOW', 'ROLE', 'viewer', 'TOOL', '*', 'tool:read_file', 'read', '{}'::jsonb, 100, true),

-- 4) Allow: viewer can search web
('P004_ALLOW_VIEWER_WEB_SEARCH', 'ALLOW', 'ROLE', 'viewer', 'TOOL', '*', 'tool:web_search', 'search', '{}'::jsonb, 100, true),

-- 5) Allow: developer can write files (ABAC path guard)
('P005_ALLOW_DEVELOPER_WRITE', 'ALLOW', 'ROLE', 'developer', 'TOOL', '*', 'tool:write_file', 'write',
 '{"path_allow_prefixes":["/mnt/user-data/workspace/","/mnt/user-data/outputs/","./"]}'::jsonb, 80, true),

-- 6) Allow: developer can replace strings (ABAC path guard)
('P006_ALLOW_DEVELOPER_REPLACE', 'ALLOW', 'ROLE', 'developer', 'TOOL', '*', 'tool:str_replace', 'write',
 '{"path_allow_prefixes":["/mnt/user-data/workspace/","/mnt/user-data/outputs/","./"]}'::jsonb, 80, true),

-- 7) Deny: ops dangerous bash patterns (ABAC)
('P007_DENY_OPS_DANGEROUS_BASH', 'DENY', 'ROLE', 'ops', 'TOOL', '*', 'tool:bash', 'execute',
 '{"bash_block_patterns":["rm -rf","sudo","shutdown","reboot","mkfs","dd if="]}'::jsonb, 20, true),

-- 8) Allow: FIN department can read finance KB
('P008_ALLOW_FIN_KB_READ', 'ALLOW', 'DEPT', 'FIN', 'KB', 'corp.cn.finance', 'kb:corp.cn.finance:*', 'read', '{}'::jsonb, 60, true),

-- 9) Deny: RND department cannot read finance KB
('P009_DENY_RND_FIN_KB', 'DENY', 'DEPT', 'RND', 'KB', 'corp.cn.finance', 'kb:corp.cn.finance:*', 'read', '{}'::jsonb, 25, true),

-- 10) Allow: admin full access (still overridable by higher-priority deny)
('P010_ALLOW_ADMIN_ALL', 'ALLOW', 'ROLE', 'admin', 'ALL', '*', '*', '*', '{}'::jsonb, 500, true);

commit;

