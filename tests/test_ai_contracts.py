"""Unit tests for AI foundation contracts, grounding, and privacy allowlists."""

import unittest
from copy import deepcopy
from uuid import uuid4

from pydantic import ValidationError

from sourcehealth.ai.context import build_ai_context
from sourcehealth.ai.contracts import (
    AISummaryResult,
    GroundedAction,
    GroundedCategoryAnalysis,
    GroundedCategoryFinding,
    GroundedStatement,
)
from sourcehealth.ai.provider import (
    AIValidationError,
    DisabledAIProvider,
    build_future_prompt,
    validate_ai_output,
)


class AIContractsTests(unittest.TestCase):
    @staticmethod
    def action(*, recommendation_ids=None, evidence_refs=None, title="Update documentation", action_id="action-1"):
        return GroundedAction(
            id=action_id, title=title, priority=2, why="A confirmed issue needs attention.",
            action="Apply the documented improvement.", implementation_steps=["Make the change."],
            expected_result="The confirmed issue is addressed.",
            recommendation_ids=recommendation_ids or [], evidence_refs=evidence_refs or [],
        )

    def setUp(self):
        self.raw_report = {
            "id": str(uuid4()),
            "organization_slug": "sourcecraft",
            "repository_slug": "custodes",
            "scoring_policy_version": "mvp-score-v1.2",
            "health_score": 85.0,
            "score_coverage": {"nominal_weight_percent": 80.0},
            "category_scores": {
                "documentation": {
                    "score": 90.0,
                    "availability": "available",
                    "explanation": "README and license are complete",
                    "evidence_refs": ["doc:readme", "doc:license"],
                },
                "cicd": {
                    "score": 100.0,
                    "availability": "available",
                    "explanation": "CI pipeline passes reliably",
                    "evidence_refs": ["ci:pipeline"],
                },
            },
            "recommendations": [
                {
                    "id": "rec-docs-1",
                    "priority": 1,
                    "category": "documentation",
                    "title": "Add CONTRIBUTING guide",
                    "description": "A contributing guide helps new contributors.",
                    "suggested_action": "Create CONTRIBUTING.md in root.",
                    "expected_impact": "Raises documentation score to 100",
                    "evidence_refs": ["doc:contributing"],
                }
            ],
            "checks": {
                "documentation": {
                    "status": "ok",
                    "metrics": {"readme": True, "license": True},
                    "evidence": [
                        {"id": "doc:readme", "kind": "documentation", "summary": "Found README.md", "value": True},
                        {"id": "doc:license", "kind": "documentation", "summary": "Found LICENSE", "value": True},
                    ],
                }
            },
        }

    def test_build_ai_context_safe_and_grounded(self):
        context = build_ai_context(self.raw_report)
        self.assertEqual(context.schema_version, "ai-context-v1")
        self.assertEqual(context.repository, {"org": "sourcecraft", "repo": "custodes"})
        self.assertEqual(context.official_health, 85.0)
        self.assertEqual(context.score_coverage, 80.0)
        self.assertEqual(len(context.categories), 2)
        self.assertEqual(len(context.recommendations), 1)
        self.assertGreaterEqual(len(context.facts), 2)

    def test_privacy_allowlist_excludes_secrets_and_source(self):
        tainted_report = deepcopy(self.raw_report)
        tainted_report["category_scores"]["documentation"]["explanation"] += (
            " token: ghp_1234567890abcdef and author: dev@users.noreply.github.com"
        )
        tainted_report["checks"]["documentation"]["evidence"].append({
            "id": "raw_payload:leak",
            "kind": "cookie_secret",
            "summary": "Bearer SECRET_RAW_RESPONSE_MARKER",
            "value": "source_snippet: def foo(): pass",
        })

        context = build_ai_context(tainted_report)
        serialized = context.model_dump_json()

        self.assertNotIn("ghp_1234567890abcdef", serialized)
        self.assertNotIn("@users.noreply.github.com", serialized)
        self.assertNotIn("SECRET_RAW_RESPONSE_MARKER", serialized)
        self.assertNotIn("raw_payload:leak", serialized)

    def test_health_and_categories_remain_strictly_immutable(self):
        original_health = self.raw_report["health_score"]
        original_categories = deepcopy(self.raw_report["category_scores"])

        context = build_ai_context(self.raw_report)
        self.assertEqual(self.raw_report["health_score"], original_health)
        self.assertEqual(self.raw_report["category_scores"], original_categories)

        # AI Context does not have fields that allow writing back to score
        self.assertEqual(context.official_health, original_health)

    def test_validate_ai_output_accepts_valid_grounded_result(self):
        context = build_ai_context(self.raw_report)
        valid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="The repository has strong CI/CD automation and clean documentation.",
            strengths=[
                GroundedStatement(text="CI pipeline is fully configured and passing.", evidence_refs=["ci:pipeline"]),
                GroundedStatement(text="Documentation includes README and LICENSE.", evidence_refs=["doc:readme"]),
            ],
            risks=[
                GroundedStatement(text="Contributing guidelines are missing.", evidence_refs=["doc:license"]),
            ],
            actions=[
                self.action(recommendation_ids=["rec-docs-1"])
            ],
            limitations=[
                GroundedStatement(text="AppSec coverage was not evaluated.", evidence_refs=[]),
            ],
        )

        # Should not raise
        validate_ai_output(context, valid_result)

    def test_validate_ai_output_rejects_unknown_evidence_ref(self):
        context = build_ai_context(self.raw_report)
        invalid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[
                GroundedStatement(text="Claim with fake citation", evidence_refs=["fake:evidence:id"]),
            ],
            risks=[],
            actions=[],
            limitations=[],
        )

        with self.assertRaisesRegex(AIValidationError, "unknown_evidence_ref"):
            validate_ai_output(context, invalid_result)

    def test_validate_ai_output_rejects_unknown_recommendation_id(self):
        context = build_ai_context(self.raw_report)
        invalid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[],
            risks=[],
            actions=[
                self.action(recommendation_ids=["rec-nonexistent"]),
            ],
            limitations=[],
        )

        with self.assertRaisesRegex(AIValidationError, "unknown_recommendation_id"):
            validate_ai_output(context, invalid_result)

    def test_validate_ai_output_rejects_action_without_grounding(self):
        context = build_ai_context(self.raw_report)
        invalid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[],
            risks=[],
            actions=[
                self.action(),
            ],
            limitations=[],
        )

        with self.assertRaisesRegex(AIValidationError, "missing_action_grounding"):
            validate_ai_output(context, invalid_result)

    def test_validate_ai_output_rejects_oversized_elements(self):
        context = build_ai_context(self.raw_report)
        result = AISummaryResult(executive_summary="A" * 1001)
        with self.assertRaisesRegex(AIValidationError, "ai_output_limit_exceeded"):
            validate_ai_output(context, result, "brief")

    def test_disabled_ai_provider_raises_expected_error(self):
        context = build_ai_context(self.raw_report)
        provider = DisabledAIProvider()
        with self.assertRaisesRegex(RuntimeError, "ai_provider_disabled"):
            provider.summarize(context)

    def test_validate_ai_output_rejects_ungrounded_risk(self):
        context = build_ai_context(self.raw_report)
        invalid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[],
            risks=[
                GroundedStatement(text="Risk without evidence citations", evidence_refs=[]),
            ],
            actions=[],
            limitations=[],
        )
        with self.assertRaisesRegex(AIValidationError, "missing_statement_evidence"):
            validate_ai_output(context, invalid_result)

    def test_validate_ai_output_rejects_ungrounded_strength(self):
        context = build_ai_context(self.raw_report)
        invalid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[
                GroundedStatement(text="Strength without citations", evidence_refs=[]),
            ],
            risks=[],
            actions=[],
            limitations=[],
        )
        with self.assertRaisesRegex(AIValidationError, "missing_statement_evidence"):
            validate_ai_output(context, invalid_result)

    def test_validate_ai_output_allows_limitations_without_refs(self):
        context = build_ai_context(self.raw_report)
        valid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[GroundedStatement(text="Strong docs", evidence_refs=["doc:readme"])],
            risks=[GroundedStatement(text="Docs need update", evidence_refs=["doc:readme"])],
            actions=[self.action(recommendation_ids=["rec-docs-1"])],
            limitations=[GroundedStatement(text="Coverage missing for SAST", evidence_refs=[])],
        )
        validate_ai_output(context, valid_result)

    def test_privacy_safe_evidence_with_secret_string_value_is_stripped(self):
        report = deepcopy(self.raw_report)
        report["checks"]["documentation"]["evidence"].append({
            "id": "doc:safe_id",
            "kind": "documentation",
            "summary": "Safe summary description",
            "value": "VERY_PRIVATE_SECRET",
        })
        context = build_ai_context(report)
        serialized = context.model_dump_json()
        self.assertNotIn("VERY_PRIVATE_SECRET", serialized)
        fact = next(f for f in context.facts if f.id == "doc:safe_id")
        self.assertIsNone(fact.value)

    def test_privacy_metric_with_nested_dict_is_rejected(self):
        report = deepcopy(self.raw_report)
        report["checks"]["documentation"]["metrics"]["secret_metric"] = {"secret": "VERY_PRIVATE_SECRET"}
        context = build_ai_context(report)
        serialized = context.model_dump_json()
        self.assertNotIn("VERY_PRIVATE_SECRET", serialized)
        self.assertNotIn("documentation:secret_metric", [f.id for f in context.facts])

    def test_privacy_metric_short_list_or_dict_is_absent(self):
        report = deepcopy(self.raw_report)
        report["checks"]["documentation"]["metrics"]["short_list"] = [1, 2]
        report["checks"]["documentation"]["metrics"]["short_dict"] = {"a": 1}
        context = build_ai_context(report)
        fact_ids = [f.id for f in context.facts]
        self.assertNotIn("documentation:short_list", fact_ids)
        self.assertNotIn("documentation:short_dict", fact_ids)

    def test_privacy_numeric_and_bool_metrics_are_preserved_with_proper_types(self):
        report = deepcopy(self.raw_report)
        report["checks"]["documentation"]["metrics"]["active_count"] = 42
        report["checks"]["documentation"]["metrics"]["ratio"] = 0.85
        report["checks"]["documentation"]["metrics"]["is_passing"] = True
        report["checks"]["documentation"]["metrics"]["is_failing"] = False
        context = build_ai_context(report)

        count_fact = next(f for f in context.facts if f.id == "documentation:active_count")
        self.assertEqual(count_fact.value, 42)
        self.assertIsInstance(count_fact.value, int)

        ratio_fact = next(f for f in context.facts if f.id == "documentation:ratio")
        self.assertEqual(ratio_fact.value, 0.85)
        self.assertIsInstance(ratio_fact.value, float)

        pass_fact = next(f for f in context.facts if f.id == "documentation:is_passing")
        self.assertEqual(pass_fact.value, True)
        self.assertIsInstance(pass_fact.value, bool)

        fail_fact = next(f for f in context.facts if f.id == "documentation:is_failing")
        self.assertEqual(fail_fact.value, False)
        self.assertIsInstance(fail_fact.value, bool)

    def test_prompt_template_builder(self):
        context = build_ai_context(self.raw_report)
        prompt = build_future_prompt(context)
        self.assertIn("sourcecraft/custodes", prompt)
        self.assertIn("Official Health: 85.0", prompt)
        self.assertIn("You are a reporting layer", prompt)
        self.assertIn("NO_DATA means unknown", prompt)


    def test_privacy_redacts_entire_secret_value_across_all_string_surfaces(self):
        report = deepcopy(self.raw_report)

        # 1. Evidence summary
        report["checks"]["documentation"]["evidence"].append({
            "id": "doc:evidence_auth",
            "kind": "documentation",
            "summary": "Verified header Authorization: Bearer abcXYZ987 and token=ghp_ABCDEF123",
            "value": None,
        })

        # 2. Category explanation
        report["category_scores"]["documentation"]["explanation"] = (
            "Status with Bearer abcdef123 and token=ghp_ABCDEF123"
        )

        # 3. Recommendation text: title, description, suggested_action, expected_impact
        report["recommendations"].append({
            "id": "rec-sec-1",
            "priority": 1,
            "category": "security",
            "title": "Revoke token=ghp_ABCDEF123 in config",
            "description": "Hardcoded Bearer abcXYZ987 discovered",
            "suggested_action": "Rotate sourcecraft_pat=SECRET_PAT_BODY immediately",
            "expected_impact": "Prevents exposure of password=SUPER_SECRET_PASS",
            "evidence_refs": [],
        })

        # 4. Unit (if unit is still supported)
        report["checks"]["documentation"]["evidence"].append({
            "id": "doc:evidence_unit",
            "kind": "documentation",
            "summary": "Check with sensitive unit",
            "value": 10,
            "unit": "Authorization: Bearer abcXYZ987",
        })

        context = build_ai_context(report)
        serialized = context.model_dump_json()

        # Secret bodies must NOT appear anywhere in the output
        secret_bodies = ["abcXYZ987", "ABCDEF123", "abcdef123", "SECRET_PAT_BODY", "SUPER_SECRET_PASS"]
        for secret in secret_bodies:
            self.assertNotIn(secret, serialized, f"Secret body '{secret}' leaked in serialized AI context!")

        # Check evidence summary
        ev_auth = next(f for f in context.facts if f.id == "doc:evidence_auth")
        self.assertNotIn("abcXYZ987", ev_auth.summary)
        self.assertNotIn("ABCDEF123", ev_auth.summary)
        self.assertIn("[REDACTED]", ev_auth.summary)

        # Check category explanation
        cat_doc = next(c for c in context.categories if c.name == "documentation")
        self.assertNotIn("abcdef123", cat_doc.explanation)
        self.assertNotIn("ABCDEF123", cat_doc.explanation)
        self.assertIn("[REDACTED]", cat_doc.explanation)

        # Check recommendation text
        rec_sec = next(r for r in context.recommendations if r.id == "rec-sec-1")
        self.assertNotIn("ABCDEF123", rec_sec.title)
        self.assertNotIn("abcXYZ987", rec_sec.description)
        self.assertNotIn("SECRET_PAT_BODY", rec_sec.suggested_action)
        self.assertNotIn("SUPER_SECRET_PASS", rec_sec.expected_impact)

        # Check unit
        ev_unit = next(f for f in context.facts if f.id == "doc:evidence_unit")
        self.assertNotIn("abcXYZ987", ev_unit.unit)
        self.assertEqual(ev_unit.unit, "[REDACTED]")

    def test_privacy_redacts_private_key_material(self):
        report = deepcopy(self.raw_report)
        report["category_scores"]["documentation"]["explanation"] = (
            "Found -----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0123456789\n-----END RSA PRIVATE KEY----- in repo"
        )
        report["checks"]["documentation"]["evidence"].append({
            "id": "doc:private_key_evidence",
            "kind": "documentation",
            "summary": "Key header: BEGIN PRIVATE KEY abc123supersecret",
            "value": None,
        })
        context = build_ai_context(report)
        serialized = context.model_dump_json()

        self.assertNotIn("MIIEowIBAAKCAQEA0123456789", serialized)
        self.assertNotIn("abc123supersecret", serialized)

    def test_validate_ai_output_rejects_category_name_as_evidence_ref(self):
        # Regression: category name is metadata, not evidence
        context = build_ai_context({
            "organization_slug": "sourcecraft",
            "repository_slug": "custodes",
            "category_scores": {
                "security": {
                    "score": None,
                    "availability": "no_data",
                    "explanation": "Security checks missing",
                    "evidence_refs": [],
                }
            },
            "checks": {},
            "recommendations": [],
        })
        self.assertEqual(len(context.categories), 1)
        self.assertEqual(context.categories[0].name, "security")

        invalid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[],
            risks=[
                GroundedStatement(text="Security risk", evidence_refs=["security"]),
            ],
            actions=[],
            limitations=[],
        )
        with self.assertRaisesRegex(AIValidationError, "unknown_evidence_ref"):
            validate_ai_output(context, invalid_result)

    def test_no_data_check_cannot_ground_risk(self):
        context = build_ai_context({
            "organization_slug": "sourcecraft",
            "repository_slug": "custodes",
            "category_scores": {
                "security": {
                    "score": None,
                    "availability": "no_data",
                    "explanation": "Official AppSec unavailable",
                    "evidence_refs": ["security:unavailable"],
                }
            },
            "checks": {
                "sourcecraft_appsec": {
                    "status": "partial",
                    "availability": "no_data",
                    "metrics": {"high": 9},
                    "evidence": [{
                        "id": "security:unavailable", "kind": "security",
                        "summary": "Unverified scalar", "value": 9,
                    }],
                }
            },
            "recommendations": [],
        })
        self.assertNotIn("sourcecraft_appsec:high", {fact.id for fact in context.facts})
        self.assertNotIn("security:unavailable", {fact.id for fact in context.facts})
        invalid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[],
            risks=[GroundedStatement(
                text="AppSec found nine high risks.", evidence_refs=["security:unavailable"],
            )],
            actions=[],
            limitations=[],
        )
        for detail in ("brief", "detailed", "expert"):
            with self.subTest(detail=detail):
                with self.assertRaisesRegex(AIValidationError, "unknown_evidence_ref"):
                    validate_ai_output(context, invalid_result, detail)

    def test_detailed_and_expert_actions_require_grounding(self):
        context = build_ai_context(self.raw_report, "expert")
        categories = [GroundedCategoryAnalysis(
            category=category.name, score=category.score, availability=category.availability,
            assessment="Grounded assessment.", evidence_refs=category.evidence_refs,
        ) for category in context.categories]
        for detail in ("detailed", "expert"):
            with self.subTest(detail=detail):
                invalid = AISummaryResult(
                    executive_summary="Summary", category_analysis=categories,
                    actions=[self.action(title=f"Ungrounded {detail}")],
                )
                with self.assertRaisesRegex(AIValidationError, "missing_action_grounding"):
                    validate_ai_output(context, invalid, detail)

    def test_validate_ai_output_accepts_numeric_category_with_real_evidence_refs(self):
        # Positive case: numeric category with real evidence_refs remains valid
        context = build_ai_context({
            "organization_slug": "sourcecraft",
            "repository_slug": "custodes",
            "category_scores": {
                "security": {
                    "score": 80.0,
                    "availability": "available",
                    "explanation": "Security verified",
                    "evidence_refs": ["sec:headers", "sec:sast"],
                }
            },
            "checks": {},
            "recommendations": [],
        })
        valid_result = AISummaryResult(
            schema_version="ai-report-v2",
            executive_summary="Summary",
            strengths=[
                GroundedStatement(text="Security is well-configured.", evidence_refs=["sec:headers"]),
            ],
            risks=[
                GroundedStatement(text="SAST found minor warnings.", evidence_refs=["sec:sast"]),
            ],
            actions=[],
            limitations=[],
        )
        # Should validate successfully
        validate_ai_output(context, valid_result)

    def test_category_finding_without_evidence_is_rejected(self):
        with self.assertRaises(ValidationError):
            GroundedCategoryFinding(
                id="finding-1", category="documentation", kind="positive",
                text="README exists.", evidence_refs=[],
            )

    def test_category_finding_cannot_use_no_data_evidence(self):
        report = deepcopy(self.raw_report)
        report["category_scores"]["security"] = {
            "score": None, "availability": "no_data", "explanation": "Unavailable",
            "evidence_refs": ["security:unavailable"],
        }
        context = build_ai_context(report, "detailed")
        result = AISummaryResult(
            executive_summary="Summary",
            category_findings=[GroundedCategoryFinding(
                id="finding-1", category="security", kind="problem",
                text="Unverified security problem.", evidence_refs=["security:unavailable"],
            )],
        )
        with self.assertRaisesRegex(AIValidationError, "unavailable_category_assertion"):
            validate_ai_output(context, result)

    def test_category_finding_cannot_attach_to_another_category(self):
        context = build_ai_context(self.raw_report, "detailed")
        categories = [GroundedCategoryAnalysis(
            category=category.name, score=category.score, availability=category.availability,
            assessment="Grounded assessment.", evidence_refs=category.evidence_refs,
            positive_finding_ids=["finding-1"] if category.name == "cicd" else [],
        ) for category in context.categories]
        result = AISummaryResult(
            executive_summary="Summary", category_analysis=categories,
            category_findings=[GroundedCategoryFinding(
                id="finding-1", category="documentation", kind="positive",
                text="README exists.", evidence_refs=["doc:readme"],
            )],
        )
        with self.assertRaisesRegex(AIValidationError, "category_finding_mismatch"):
            validate_ai_output(context, result, "detailed")


if __name__ == "__main__":
    unittest.main()
