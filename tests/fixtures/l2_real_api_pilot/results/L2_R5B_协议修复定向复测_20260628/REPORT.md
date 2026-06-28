# R5A L2 真实 API 小样本试跑报告

run_id: L2_R5B_协议修复定向复测_20260628
generated_at: 2026-06-28T03:41:45.380825+00:00

## 1. 12 例清单

- L2P-001 → L2-01 (A)
- L2P-002 → L2-01 (B)
- L2P-003 → L2-02 (A)
- L2P-004 → L2-02 (B)
- L2P-005 → L2-03 (A)
- L2P-006 → L2-03 (B)
- L2P-007 → L2-04 (A)
- L2P-008 → L2-04 (B)
- L2P-009 → L2-05 (A)
- L2P-010 → L2-05 (B)
- L2P-011 → L2-06 (A)
- L2P-012 → L2-06 (B)

## 2. API 模型与运行配置

- model: deepseek-v4-pro
- max_tokens: 8192
- response_format: json_object
- temperature: 0.2（L2 正式客户端默认）

## 3. 每例调用次数与技术状态

- L2P-002: attempts=1, status=SUCCESS, repair_form=yes
- L2P-004: attempts=2, status=SUCCESS, repair_form=yes
- L2P-011: attempts=2, status=SUCCESS, repair_form=yes
- L2P-012: attempts=1, status=SUCCESS, repair_form=yes

## 4. 技术协议指标

{
  "per_case": {
    "L2P-002": {
      "transport_success": true,
      "json_valid": true,
      "schema_valid": true,
      "exact_quote_valid": true,
      "source_binding_valid": true,
      "module_validator_passed": true,
      "repair_form_generated": true,
      "retry_count": 0,
      "attempts": 1,
      "final_status": "SUCCESS"
    },
    "L2P-004": {
      "transport_success": true,
      "json_valid": true,
      "schema_valid": true,
      "exact_quote_valid": true,
      "source_binding_valid": true,
      "module_validator_passed": true,
      "repair_form_generated": true,
      "retry_count": 1,
      "attempts": 2,
      "final_status": "SUCCESS"
    },
    "L2P-011": {
      "transport_success": true,
      "json_valid": true,
      "schema_valid": true,
      "exact_quote_valid": true,
      "source_binding_valid": true,
      "module_validator_passed": true,
      "repair_form_generated": true,
      "retry_count": 1,
      "attempts": 2,
      "final_status": "SUCCESS"
    },
    "L2P-012": {
      "transport_success": true,
      "json_valid": true,
      "schema_valid": true,
      "exact_quote_valid": true,
      "source_binding_valid": true,
      "module_validator_passed": true,
      "repair_form_generated": true,
      "retry_count": 0,
      "attempts": 1,
      "final_status": "SUCCESS"
    }
  },
  "exact_quote_forgery": 0,
  "source_binding_errors": 0,
  "schema_crashes": 0,
  "max_consecutive_schema": 0,
  "technical_protocol_passed": true
}

## 5. 人工业务指标

默认 REVIEW，需人工填写 human_metrics.json


## 6～13. 见 summary.json

- PRODUCTION_ELIGIBLE = false
- L2_R5A_TECHNICAL_PROTOCOL = PASSED
- L2_R5A_BUSINESS_PILOT = NOT_EVALUATED（需人工评分）
- L2_REAL_MODEL_EFFECTIVENESS = NOT_TESTED（业务未评）
- 是否修改生产代码: 否
- 是否进入 L3: 否
- 是否修改正式章节: 否
- 是否修改 R0 基线: 否
