---
name: sandbox-write-test
skill_id: sandbox.write_test
display_name: Sandbox 写入测试
provider: local_script
priority: 999
depends_on: []
trigger_keywords: []
input_schema: {}
example_payload: {}
sandbox_policy: {"timeout_seconds": 5, "memory_mb": 128, "cpu_seconds": 2, "max_open_files": 16, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Internal test skill for validating sandbox write restrictions.
---

# Sandbox Write Test Skill

Internal test-only skill.
