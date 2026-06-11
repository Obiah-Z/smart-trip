---
name: sandbox-timeout-test
skill_id: sandbox.timeout_test
display_name: Sandbox 超时测试
provider: local_script
priority: 999
depends_on: []
trigger_keywords: []
input_schema: {}
example_payload: {}
sandbox_policy: {"timeout_seconds": 1, "memory_mb": 128, "cpu_seconds": 1, "max_open_files": 16, "allow_network": false, "allow_subprocess": false, "writable_roots": []}
description: Internal test skill for validating sandbox timeout enforcement.
---

# Sandbox Timeout Test Skill

Internal test-only skill.
