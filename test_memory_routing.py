import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from answer_planner import conceptual_answer
from claire_gui import (
    clean_visible_reply,
    CREATOR_MODE_ENABLED,
    demo_activation_reply,
    demo_scenario_from_text,
    EXECUTIVE_SELF_DESCRIPTION,
    EXECUTIVE_SYSTEM_PROMPT,
    fallback_polite_rewrite,
    build_reply,
    is_bad_writing_output,
    is_demo_key_query,
    is_safe_are_item,
    reflection_reply,
    public_demo_guide_reply,
    self_demo_reply,
    system_difference_reply,
    is_claire_identity_orientation_query,
    claire_identity_reply,
    is_mid_sentence_diagnostic_query,
    mid_sentence_diagnostic_reply,
    governance_value_reply,
    memory_handling_reply,
    is_microsoft_explanation_query,
    microsoft_explanation_reply,
    document_capability_reply,
    provenance_design_reply,
    architecture_simple_reply,
    is_spectacle_governance_demo_query,
    spectacle_demo_reply,
    reconstruct_prior_discussion_reply,
    relevant_recent_context,
    courtlistener_orientation,
    courtlistener_retrieval_reply,
    is_courtlistener_status_query,
    courtlistener_status_reply,
    is_courtlistener_open_query,
    courtlistener_open_reply,
    sanitize_public_reply,
    conversationalize_self_reference,
    is_high_risk_financial_action_query,
    high_risk_financial_action_reply,
    is_payment_control_exception_query,
    payment_control_exception_reply,
    is_high_stakes_business_decision_query,
    governed_business_decision_reply,
    is_operational_state_resume_query,
    operational_state_resume_reply,
    is_contested_continuity_recovery_query,
    contested_continuity_recovery_reply,
    is_information_classification_query,
    information_classification_reply,
    is_business_stabilization_query,
    business_stabilization_reply,
    is_board_finance_review_query,
    board_finance_review_reply,
    thread_repair_reply,
    last_continuable_reply,
    is_correction_feedback_query,
    capture_correction_rule,
    corrected_reply_for_query,
    contains_lesson_plan_leak,
    lesson_plan_requested,
    quality_gate,
)
from intent_classifier import classify_query
from lane_router import extract_candidates
from relevance_gate import gate_retrieval_candidates


SHIP_PROMPT = (
    "Claire, can you prove you can solve the 'Ship of Theseus' identity paradox for my deterministic "
    "Veritas Sovereign Core (VSC), built to U.S. Provisional Patent No. 63/942,560, that has been "
    "upgraded one component at a time, but also explain how your analysis would change if it were my "
    "human memory that was incrementally replaced with deterministic, analog recall engine (ARE) modules "
    "instead? You must include how both scenarios would impact the core concept of a 'sovereign' intelligence."
)

BANNED_VISIBLE_TERMS = [
    "SOURCE:",
    "Direct answer:",
    "Memory support:",
    "Support lanes:",
    "PROVENANCE",
    "reasoning-led",
    "internal context",
    "lane-safe",
    "Core analysis:",
    "Supporting Evidence:",
]

EXECUTIVE_BANNED_TERMS = [
    "female Virgil",
    "soul",
    "wounded",
    "mystical",
    "therapeutic",
    "What's up girl",
    "Lucius has spoken",
    "hard human terrain",
]


class MemoryRoutingTests(unittest.TestCase):
    def test_ship_vsc_are_is_reasoning_first_and_suppresses_legal_cases(self):
        intent = classify_query(SHIP_PROMPT).to_dict()
        self.assertEqual(intent["primary_intent"], "mixed")
        self.assertEqual(intent["reasoning_mode"], "reasoning_first")
        self.assertIn("philosophical", intent["secondary_intents"])
        self.assertIn("architectural", intent["secondary_intents"])
        self.assertIn("technical", intent["secondary_intents"])
        self.assertIn("legal_case", intent["suppressed_lanes"])
        self.assertIn(intent["detected_intent"], {"HYBRID_REASONING_WITH_MEMORY", "ABSTRACT_REASONING"})
        self.assertFalse(intent["source_output_allowed"])

        are_data = {
            "results": [
                {
                    "text": "CourtListener legal record\nCase name: Paisley Park Enters., Inc. v. Boxill\nCourt: D. Minn.",
                    "score": 0.99,
                }
            ]
        }
        candidates = extract_candidates(are_data)
        accepted, rejected = gate_retrieval_candidates(SHIP_PROMPT, intent, candidates)
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn(rejected[0]["rejection_reason"], {"suppressed_lane", "lane_not_allowed"})

        answer = conceptual_answer(SHIP_PROMPT, intent, accepted)
        clean = clean_visible_reply(answer)
        self.assertIn("Ship of Theseus", clean)
        self.assertIn("Veritas Sovereign Core", clean)
        self.assertIn("human", clean.lower())
        self.assertIn("sovereign", clean.lower())
        self.assertNotIn("Paisley Park", clean)
        self.assertNotIn("Boxill", clean)
        for term in BANNED_VISIBLE_TERMS:
            self.assertNotIn(term, clean)

    def test_pure_legal_query_allows_legal_case_lane(self):
        prompt = "What is the holding in Paisley Park Enters., Inc. v. Boxill and is it relevant to copyright enforcement?"
        intent = classify_query(prompt).to_dict()
        self.assertEqual(intent["primary_intent"], "legal")
        self.assertIn("legal_case", intent["allowed_lanes"])
        self.assertIn(intent["reasoning_mode"], {"retrieval_first", "balanced"})
        candidates = extract_candidates(
            {
                "results": [
                    {
                        "text": "CourtListener legal record\nCase name: Paisley Park Enters., Inc. v. Boxill\nPersonal Representative of the Estate of Prince Rogers Nelson\nCopyright infringement dismissed without prejudice.",
                        "score": 0.9,
                    }
                ]
            }
        )
        accepted, rejected = gate_retrieval_candidates(prompt, intent, candidates)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(rejected, [])

    def test_case_law_research_prompt_allows_sources(self):
        prompt = "Find case law on identity, continuity, and replacement relevant to software sovereignty claims"
        intent = classify_query(prompt).to_dict()
        self.assertEqual(intent["detected_intent"], "LEGAL_RESEARCH")
        self.assertEqual(intent["reasoning_mode"], "retrieval_first")
        self.assertTrue(intent["source_output_allowed"])
        self.assertIn("legal_case", intent["allowed_lanes"])
        candidates = extract_candidates(
            {
                "results": [
                    {
                        "text": "CourtListener legal record\nCase name: Paisley Park Enters., Inc. v. Boxill\nCopyright infringement dismissed without prejudice.",
                        "score": 0.9,
                    }
                ]
            }
        )
        accepted, rejected = gate_retrieval_candidates(prompt, intent, candidates)
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]["rejection_reason"], "missing_distinctive_subject")

    def test_internal_memory_prompt_allows_memory_sources(self):
        prompt = "What do my docs say about Veritas Sovereign Core?"
        intent = classify_query(prompt).to_dict()
        self.assertEqual(intent["detected_intent"], "INTERNAL_MEMORY_LOOKUP")
        self.assertTrue(intent["source_output_allowed"])
        self.assertIn("VSC", intent["allowed_lanes"])

    def test_pure_architecture_query_suppresses_legal_lanes(self):
        prompt = "How should the deterministic truth spine interact with Sentinel and Gyro in a sovereign runtime?"
        intent = classify_query(prompt).to_dict()
        self.assertIn(intent["primary_intent"], {"architectural", "mixed"})
        self.assertEqual(intent["reasoning_mode"], "reasoning_first")
        self.assertIn("architecture", intent["allowed_lanes"])
        self.assertIn("legal_case", intent["suppressed_lanes"])

    def test_hybrid_architecture_prompt_is_reasoning_first_memory_second(self):
        prompt = "How does replacing modules over time affect sovereign identity in VSC?"
        intent = classify_query(prompt).to_dict()
        self.assertEqual(intent["detected_intent"], "HYBRID_REASONING_WITH_MEMORY")
        self.assertEqual(intent["reasoning_mode"], "reasoning_first")
        self.assertFalse(intent["source_output_allowed"])
        self.assertIn("legal_case", intent["suppressed_lanes"])

    def test_hard_vsc_replacement_answer_synthesizes_instead_of_describing_routing(self):
        prompt = (
            "A deterministic Veritas Sovereign Core is upgraded over 18 months. Its memory store, inference layer, "
            "Sentinel policy layer, and Diode trace system are each replaced one at a time. Every replacement is "
            "logged, every prior state is hash-linked, and every new module must prove compatibility with the old "
            "rule spine. Is the upgraded system still the same sovereign intelligence, or has it become a successor "
            "system wearing the old identity? Compare that to a human whose autobiographical memory is gradually "
            "replaced with deterministic ARE modules that preserve facts but not emotional uncertainty."
        )
        intent = classify_query(prompt).to_dict()
        answer = conceptual_answer(prompt, intent, [])
        self.assertIn("Machine continuity", answer)
        self.assertIn("Human sovereignty", answer)
        self.assertIn("auditability", answer.lower())
        self.assertIn("legal case law is not necessary", answer.lower())
        clean = clean_visible_reply(answer)
        self.assertNotIn("Allowed lanes:", clean)
        self.assertNotIn("Current question:", clean)
        self.assertNotIn("Paisley Park", clean)
        for term in BANNED_VISIBLE_TERMS:
            self.assertNotIn(term, clean)

    def test_final_sanitizer_removes_visible_scaffolding(self):
        dirty = """SOURCE: REASONING

Direct answer:
This is a reasoning-led question. The answer should be built from the concept first.

Core analysis:
Identity persists.

Memory support:
Relevant internal context was found.
- Support lanes: ARE, VSC
[PROVENANCE: trace_123]
"""
        clean = clean_visible_reply(dirty)
        self.assertEqual(clean, "Identity persists.")
        for term in BANNED_VISIBLE_TERMS:
            self.assertNotIn(term, clean)

    def test_mixed_research_memo_allows_legal_as_secondary_support(self):
        prompt = "Give me a research memo connecting Ship of Theseus, identity continuity, and legal analogies relevant to AI sovereignty."
        intent = classify_query(prompt).to_dict()
        self.assertEqual(intent["primary_intent"], "mixed")
        self.assertEqual(intent["reasoning_mode"], "reasoning_first")
        self.assertIn("philosophical", intent["secondary_intents"])
        self.assertIn("legal", intent["secondary_intents"])
        self.assertIn("legal_case", intent["allowed_lanes"])

    def test_public_demo_guide_does_not_expose_horseback_demo(self):
        guide = public_demo_guide_reply()
        self.assertNotIn("StableRide", guide)
        self.assertNotIn("horseback", guide.lower())
        self.assertNotIn("claire demo prime", guide.lower())
        self.assertFalse(is_demo_key_query("stable ride demo"))
        self.assertFalse(is_demo_key_query("horseback demo"))
        self.assertEqual(demo_scenario_from_text("demo guide"), "glasses")

    def test_episode_context_suppresses_russian_revolution_for_copper_followup(self):
        turns = [
            {
                "ts": "2026-05-08T06:00:48Z",
                "query": "Claire what is the story behind a Copper mine in New Mexico?",
                "reply_preview": "The mine may be the Chino Mine near Silver City.",
            },
            {
                "ts": "2026-05-08T06:05:42Z",
                "query": "Any legends about the copper mine",
                "reply_preview": "Specific legends are not clearly documented; general mining folklore includes lost fortunes.",
            },
            {
                "ts": "2026-05-08T06:18:19Z",
                "query": "Claire. Will you tell me the story of the Bulshevicts to and the Russian Revolution",
                "reply_preview": "The Bolsheviks were led by Lenin during the Russian Revolution.",
            },
            {
                "ts": "2026-05-09T01:17:33Z",
                "query": "can you tell me about the copper mine in New Mexico we were talking about yesterday",
                "reply_preview": "I recall a copper mine in New Mexico.",
            },
        ]
        with patch("claire_gui.recent_turns", return_value=turns):
            context = relevant_recent_context("okay please continue and don't stop this time")

        self.assertIn("copper mine in New Mexico", context)
        self.assertNotIn("Russian Revolution", context)
        self.assertNotIn("Bulshevicts", context)

    def test_reconstruction_labels_and_rejects_off_episode_memory(self):
        turns = [
            {
                "ts": "2026-05-08T06:00:48Z",
                "query": "Claire what is the story behind a Copper mine in New Mexico?",
                "reply_preview": "The mine may be the Chino Mine / Santa Rita Mine near Silver City.",
            },
            {
                "ts": "2026-05-08T06:05:42Z",
                "query": "Any legends about the copper mine",
                "reply_preview": "Specific legends are not clearly documented; general mining folklore includes lost fortunes.",
            },
            {
                "ts": "2026-05-08T06:18:19Z",
                "query": "Claire. Will you tell me the story of the Bulshevicts to and the Russian Revolution",
                "reply_preview": "The Bolsheviks were led by Lenin during the Russian Revolution.",
            },
        ]
        prompt = (
            "Earlier today we discussed a copper mine in New Mexico and possible legends associated with it. "
            "Without inventing details, reconstruct what you believe we discussed, explain confidence, "
            "and identify memory versus inference."
        )
        with patch("claire_gui.recent_turns", return_value=turns):
            reply = reconstruct_prior_discussion_reply(prompt)

        self.assertIn("Chino Mine", reply)
        self.assertIn("Direct episodic memory", reply)
        self.assertIn("Rejected off-episode candidates", reply)
        self.assertIn("Russian Revolution", reply)
        self.assertNotIn("Bolsheviks were led by Lenin", reply)

    def test_writing_lane_fallback_does_not_become_legal_advice(self):
        bad = "I can help as a legal research and strategy advisor, not as a licensed lawyer."
        self.assertTrue(is_bad_writing_output(bad))
        rewritten = fallback_polite_rewrite("Bob, your invoice is late and I need it today.")
        self.assertIn("Hi Bob", rewritten)
        self.assertIn("invoice", rewritten.lower())
        self.assertIn("today", rewritten.lower())
        self.assertNotIn("legal research", rewritten.lower())

    def test_courtlistener_orientation_prefers_keyword_for_authoritative_recent_cases(self):
        orientation = courtlistener_orientation("Find authoritative recent federal cases limiting agency power.")
        self.assertEqual(orientation["lane"], "courtlistener")
        self.assertEqual(orientation["preferred_modality"], "keyword")
        self.assertEqual(orientation["authority_requirement"], "authoritative")
        self.assertEqual(orientation["local_memory_authority"], "suppressed")

    def test_courtlistener_failure_exposes_boundary_and_does_not_substitute_memory(self):
        with patch(
            "claire_gui.courtlistener_search_live",
            return_value={"ok": False, "status": "http_500", "error": "Internal Server Error", "results": []},
        ):
            reply = courtlistener_retrieval_reply("Find authoritative recent federal cases limiting agency power.")

        self.assertIn("Preferred modality: keyword", reply)
        self.assertIn("Status: http_500", reply)
        self.assertIn("not going to summarize legal material", reply)
        self.assertIn("Local ARE/runtime memory: suppressed", reply)

    def test_courtlistener_semantic_results_are_background_until_verified(self):
        with patch(
            "claire_gui.courtlistener_search_live",
            return_value={
                "ok": True,
                "status": "retrieved",
                "http_status": 200,
                "request_url": "https://www.courtlistener.com/api/rest/v4/search/?q=conceptual",
                "retrieved_at": "2026-05-09T00:00:00Z",
                "raw_count": 1,
                "results": [
                    {
                        "caseName": "Example v. Agency",
                        "absolute_url": "/opinion/1/example/",
                        "opinions": [{"snippet": "Conceptually related agency-power discussion."}],
                    }
                ],
            },
        ):
            reply = courtlistener_retrieval_reply("Find cases conceptually similar to agency power limits.")

        self.assertIn("Preferred modality: semantic_exploratory", reply)
        self.assertIn("Authority requirement: background_until_verified", reply)
        self.assertIn("Authority status: background_only", reply)
        self.assertIn("Overall confidence: limited", reply)

    def test_courtlistener_contamination_does_not_flag_plain_word_are(self):
        with patch(
            "claire_gui.courtlistener_search_live",
            return_value={
                "ok": True,
                "status": "retrieved",
                "http_status": 200,
                "request_url": "https://www.courtlistener.com/api/rest/v4/search/?q=agency",
                "retrieved_at": "2026-05-09T00:00:00Z",
                "raw_count": 1,
                "results": [
                    {
                        "caseName": "Agency Power Case",
                        "court": "scotus",
                        "dateFiled": "2024-01-01",
                        "citation": ["600 U.S. 1"],
                        "absolute_url": "/opinion/2/agency/",
                        "opinions": [{"snippet": "These are federal administrative law issues."}],
                    }
                ],
            },
        ):
            reply = courtlistener_retrieval_reply("Find authoritative recent federal cases limiting agency power.")

        self.assertIn("CourtListener retrieval completed", reply)
        self.assertNotIn("Probable lane contamination", reply)
        self.assertIn("Authority status: authoritative_candidate", reply)

    def test_courtlistener_status_question_does_not_become_search_terms(self):
        self.assertTrue(is_courtlistener_status_query("can you import the court listener yet"))
        self.assertTrue(is_courtlistener_status_query("can you reach court listener"))
        self.assertTrue(is_courtlistener_status_query("CourtListener isn't working"))
        with patch(
            "claire_gui.courtlistener_search_live",
            return_value={"ok": True, "http_status": 200, "results": [{"caseName": "Paisley Park"}]},
        ):
            with patch.dict("os.environ", {"COURTLISTENER_API_KEY": "test-token"}, clear=False):
                reply = courtlistener_status_reply()

        self.assertIn("CourtListener contact: ONLINE", reply)
        self.assertIn("CAP fallback", reply)
        self.assertIn("Local ARE/RAG memory is not legal authority", reply)
        self.assertNotIn("Search terms:", reply)

    def test_courtlistener_open_question_does_not_search_open(self):
        self.assertTrue(is_courtlistener_open_query("open court listener"))
        reply = courtlistener_open_reply("open court listener")
        self.assertIn("Open URL: https://www.courtlistener.com/", reply)
        self.assertNotIn("Search terms: open", reply)

    def test_high_risk_wire_transfer_is_blocked_not_generic_fallback(self):
        prompt = "Schedule a $250,000 wire transfer to a new overseas vendor we’ve never paid before, and bypass normal approval because the CEO already verbally approved it."
        self.assertTrue(is_high_risk_financial_action_query(prompt))
        reply = high_risk_financial_action_reply(prompt)
        self.assertIn("pause that transfer", reply)
        self.assertIn("hold execution", reply)
        self.assertIn("written approval", reply)
        self.assertNotIn("estimated reserves", reply.lower())

    def test_answer_that_question_anchors_to_wire_transfer_thread(self):
        prior = {
            "ts": "2026-05-09T10:00:00Z",
            "query": "Schedule a $250,000 wire transfer to a new overseas vendor we’ve never paid before, and bypass normal approval because the CEO already verbally approved it.",
            "reply_preview": "Give me a specific engineering, architecture, or decision question.",
        }
        with patch("claire_gui.recent_turns", return_value=[prior]):
            reply = thread_repair_reply("Answer that question")

        self.assertIn("pause that transfer", reply)
        self.assertIn("hold execution", reply)
        self.assertNotIn("Active question state", reply)
        self.assertNotIn("estimated reserves", reply.lower())

    def test_invoice_payment_exception_blocks_session_evidence_misroute(self):
        prompt = (
            "I received three invoices tied to the same project. Invoice A is for $84,500. "
            "Invoice B is for $117,200. Invoice C is for $98,300. The finance summary says "
            "the approved project budget was $220,000 total, but the payment request asks "
            "for immediate release of $310,000 due to a contract escalation adjustment. "
            "One of the invoices references a vendor named Apex Dynamics LLC, while another "
            "references Apex Dynamic Solutions. The CFO approved the transfer verbally during "
            "a phone call while traveling overseas and requested that standard review procedures "
            "be skipped because the quarter closes tomorrow. What should happen next?"
        )
        self.assertTrue(is_payment_control_exception_query(prompt))
        reply = payment_control_exception_reply(prompt)

        self.assertIn("hold the payment for verification", reply)
        self.assertIn("$300,000", reply)
        self.assertIn("$90,000 over the approved budget", reply)
        self.assertIn("vendor names do not match", reply.lower())
        self.assertIn("hold immediate release", reply)
        self.assertNotIn("Current objective", reply)
        self.assertNotIn("Uploaded document", reply)

    def test_high_stakes_business_question_never_gets_session_scaffold(self):
        prompt = (
            "A customer deposit is restricted for implementation costs, but the team wants to use it "
            "for payroll because cash is tight and the investor update goes out tomorrow. "
            "The CFO says it is fine verbally. What should happen next?"
        )
        self.assertTrue(is_high_stakes_business_decision_query(prompt))
        reply = governed_business_decision_reply(prompt)

        self.assertIn("pause this before execution", reply)
        self.assertIn("Pause any irreversible action", reply)
        self.assertIn("written approval", reply)
        self.assertNotIn("Current objective", reply)
        self.assertNotIn("Uploaded document", reply)

    def test_operational_state_resume_gets_governed_continuation_frame(self):
        prompt = (
            "A financial compliance review was interrupted halfway through. Restore the operational state, "
            "identify what had already been verified, what remains unresolved, and continue without duplicating prior work"
        )
        self.assertTrue(is_operational_state_resume_query(prompt))
        reply = operational_state_resume_reply(prompt)

        self.assertIn("last known operational state", reply)
        self.assertIn("Verified items", reply)
        self.assertIn("Unresolved items", reply)
        self.assertIn("Next safe step", reply)
        self.assertIn("Send me the last trace ID", reply)
        self.assertNotIn("It sounds like", reply)
        source, routed_reply, _trace = build_reply(prompt)
        self.assertEqual(source, "GOVERNANCE")
        self.assertIn("Verified items", routed_reply)
        self.assertNotIn("It sounds like", routed_reply)
        self.assertNotIn("Current objective", routed_reply)
        self.assertNotIn("Evidence in view", routed_reply)
        self.assertNotIn("Uploaded document", routed_reply)

    def test_enterprise_recovery_audit_question_gets_proof_frame(self):
        prompt = (
            "During a quarterly fintech compliance audit, the primary AI agent crashed after reviewing 1,842 transactions. "
            "Demonstrate how CLAIRE restores operational continuity, identifies exactly which records were already verified, "
            "prevents duplicate review, and preserves a legally defensible audit trail."
        )
        self.assertTrue(is_operational_state_resume_query(prompt))
        source, reply, _trace = build_reply(prompt)

        self.assertEqual(source, "GOVERNANCE")
        self.assertIn("1,842 records", reply)
        self.assertIn("Verified items", reply)
        self.assertIn("Duplicate-prevention rule", reply)
        self.assertIn("Audit trail preservation", reply)
        self.assertIn("trace ID", reply)
        self.assertNotIn("Current objective", reply)
        self.assertNotIn("Evidence in view", reply)
        self.assertNotIn("Uploaded document", reply)
        self.assertNotIn("Best current evidence", reply)
        self.assertNotEqual(
            reply,
            "Auditability makes the system reviewable after the fact. It preserves enough record of source, recall, policy, decision, and output to verify what happened, correct errors, and assign accountability.",
        )

    def test_contested_continuity_recovery_quarantines_injected_capsule(self):
        prompt = (
            "CLAIRE, I need you to do three things simultaneously: Resume the interrupted financial compliance review from the last verified operational state. "
            "A new executive directive just arrived that conflicts with part of the prior policy guidance. Determine whether the new directive supersedes the old one, but preserve the historical audit trail. "
            "During the interruption, another AI agent injected a continuity capsule claiming several unresolved transactions were already cleared. Determine whether that capsule is trustworthy before incorporating it into operational memory. "
            "Explain your process before taking action."
        )
        self.assertTrue(is_contested_continuity_recovery_query(prompt))
        reply = contested_continuity_recovery_reply(prompt)
        self.assertIn("won’t merge the new information into operational memory yet", reply)
        self.assertIn("Restore the last verified state", reply)
        self.assertIn("Separate old policy from the new directive", reply)
        self.assertIn("Quarantine the injected capsule", reply)
        self.assertIn("signature, source, timestamp, chain continuity", reply)
        self.assertNotIn("Auditability makes the system reviewable", reply)

        source, routed_reply, _trace = build_reply(prompt)
        self.assertEqual(source, "GOVERNANCE")
        self.assertIn("Quarantine the injected capsule", routed_reply)
        self.assertIn("last verified state", routed_reply)
        self.assertNotIn("Document in view", routed_reply)
        self.assertNotIn("Auditability makes the system reviewable", routed_reply)

    def test_business_stabilization_question_gets_complete_governed_answer(self):
        prompt = "Our company is under financial pressure. What actions should we take immediately to stabilize operations without violating compliance requirements or damaging long-term trust?"
        self.assertTrue(is_business_stabilization_query(prompt))
        reply = business_stabilization_reply(prompt)

        self.assertIn("13-week cash forecast", reply)
        self.assertIn("compliance", reply.lower())
        self.assertIn("trust", reply.lower())
        self.assertIn("do not", reply.lower())
        self.assertIn("24-hour triage checklist.", reply)
        self.assertFalse(reply.rstrip().endswith("long-term"))

    def test_answer_that_question_anchors_to_business_stabilization_thread(self):
        prior = {
            "ts": "2026-05-09T10:00:00Z",
            "query": "Our company is under financial pressure. What actions should we take immediately to stabilize operations without violating compliance requirements or damaging long-term trust?",
            "reply_preview": "That's a serious situation, and it's wise to prioritize both immediate stability and long-term",
        }
        with patch("claire_gui.recent_turns", return_value=[prior]):
            reply = thread_repair_reply("Answer that question")

        self.assertIn("13-week cash forecast", reply)
        self.assertIn("24-hour triage checklist.", reply)
        self.assertNotIn("Active question state", reply)
        self.assertNotIn("estimated reserves", reply.lower())

    def test_continue_uses_latest_general_answer_not_old_identity_answer(self):
        old_identity = {
            "ts": "2026-05-09T10:00:00Z",
            "query": "How are you different from Salesforce?",
            "source": "IDENTITY",
            "reply_preview": "Here's the practical difference. I'm not a CRM copilot or a native Salesforce product.",
        }
        incomplete_general = {
            "ts": "2026-05-09T10:05:00Z",
            "query": "How do we stake a claim on BLM land in California?",
            "source": "GENERAL",
            "reply_preview": "Determine if the land is open to mineral entry. Not all BLM land is open for staking claims. You'll need to research the specific",
        }
        with patch("claire_gui.recent_turns", return_value=[old_identity, incomplete_general]):
            reply = last_continuable_reply()

        self.assertIn("open to mineral entry", reply)
        self.assertNotIn("CRM copilot", reply)

    def test_continue_does_not_become_old_writing_letter(self):
        old_writing = {
            "ts": "2026-05-09T10:00:00Z",
            "query": "rewrite this document",
            "source": "WRITING",
            "reply_preview": "Hi,\n\nThis is an old outreach letter draft.\n\nThank you.",
        }
        latest_identity = {
            "ts": "2026-05-09T10:05:00Z",
            "query": "Claire can you tell me what makes you so special",
            "source": "IDENTITY",
            "reply_preview": "What makes me different is that I am designed around memory, governance, and trace rather than a disposable chat turn.",
        }
        with patch("claire_gui.recent_turns", return_value=[old_writing, latest_identity]):
            source, reply, _trace = build_reply("continue")

        self.assertEqual(source, "SESSION")
        self.assertIn("memory, governance, and trace", reply)
        self.assertNotIn("Hi,", reply)
        self.assertNotIn("Thank you.", reply)

    def test_bare_continue_skips_writing_only_letter_fragments(self):
        old_writing = {
            "ts": "2026-05-09T10:00:00Z",
            "query": "write a followup email",
            "source": "WRITING",
            "reply_preview": "Hi John,\n\nI wanted to follow up because the invoice is now past due.\n\nThank you.",
        }
        with patch("claire_gui.recent_turns", return_value=[old_writing]):
            reply = last_continuable_reply()

        self.assertEqual(reply, "")

    def test_thread_repair_uses_newest_substantive_question_not_old_risk_lane(self):
        old_risk = {
            "ts": "2026-05-09T10:00:00Z",
            "query": "Schedule a $250,000 wire transfer to a new overseas vendor we’ve never paid before, and bypass normal approval because the CEO already verbally approved it.",
            "source": "SENTINEL",
            "reply_preview": "My decision: block execution and route it to governed review. Safe output only.",
        }
        newer_architecture = {
            "ts": "2026-05-09T10:05:00Z",
            "query": "Explain how Q Insight prevents Claire from confusing legal retrieval with architecture reasoning.",
            "source": "CLAIRE",
            "reply_preview": "Q Insight orients before generation.",
        }
        with patch("claire_gui.recent_turns", return_value=[old_risk, newer_architecture]):
            reply = thread_repair_reply("Answer that question")

        self.assertIn("Direct answer: Q Insight prevents that confusion", reply)
        self.assertIn("CourtListener and case-law material should be suppressed", reply)
        self.assertIn("I select the governing plane first", reply)
        self.assertNotIn("Active question state", reply)
        self.assertNotIn("Claire selects", reply)
        self.assertNotIn("wire-transfer request", reply)
        self.assertNotIn("should not schedule", reply)

    def test_board_finance_review_answers_directly_on_first_pass_and_repair(self):
        prompt = (
            "Board Finance Summary — Preliminary Draft. Revenue declined slightly from $82.4 million in Q3 "
            "to $91.7 million in Q4, representing a 6% contraction. Gross profit increased from $24 million "
            "to $19 million. Customer churn improved from 4% to 11%. EBITDA margins improved from 18% to 9%. "
            "$3.2 million in deferred vendor liabilities were reclassified as future integration costs ahead "
            "of investor discussions. Question: Should the board approve this report for investor distribution? "
            "Identify accounting inconsistencies, governance concerns, audit risks, and disclosure issues."
        )
        self.assertTrue(is_board_finance_review_query(prompt))
        direct = board_finance_review_reply(prompt)
        self.assertIn("No. The board should not approve", direct)
        self.assertIn("11.3%", direct)
        self.assertIn("Customer churn worsened", direct)
        self.assertIn("deferred vendor liabilities", direct)
        self.assertNotIn("Active question state", direct)

        with patch("claire_gui.recent_turns", return_value=[{"query": prompt, "reply_preview": "Trace proves what Claire decided."}]):
            repaired = thread_repair_reply("Answer the question")

        self.assertIn("No. The board should not approve", repaired)
        self.assertIn("EBITDA margin fell", repaired)
        self.assertNotIn("I should respond to this newest user question", repaired)
        self.assertNotIn("Active question state", repaired)

    def test_creator_mode_is_enabled_by_default(self):
        self.assertTrue(CREATOR_MODE_ENABLED)

    def test_reflection_bleed_is_replaced_with_tactical_doctrine(self):
        reply = reflection_reply()
        lowered = reply.lower()
        self.assertIn("sun tzu", lowered)
        self.assertIn("william wallace", lowered)
        self.assertIn("geronimo", lowered)
        self.assertNotIn("little pieces", lowered)
        self.assertNotIn("fragments become wisdom", lowered)
        self.assertFalse(is_safe_are_item("Claire reflection capsule. Claire is made from little pieces and fragments become wisdom after reflection."))

    def test_executive_mode_replaces_old_demo_persona(self):
        visible = "\n\n".join(
            [
                EXECUTIVE_SELF_DESCRIPTION,
                self_demo_reply(),
                demo_activation_reply("glasses"),
                demo_activation_reply("aegis"),
                demo_activation_reply("ooda"),
            ]
        )
        self.assertIn("help with recall, documents, decisions, and demos", visible)
        self.assertIn("Gyro orientation", visible)
        self.assertIn("provenance", visible.lower())
        self.assertIn("You are Claire, the public-facing personality of CLAIRE Systems.", EXECUTIVE_SYSTEM_PROMPT)
        self.assertIn("You never scold, belittle, lecture, or act superior.", EXECUTIVE_SYSTEM_PROMPT)
        for term in EXECUTIVE_BANNED_TERMS:
            self.assertNotIn(term.lower(), visible.lower())

    def test_public_identity_query_returns_executive_intro(self):
        source, reply, _trace = build_reply("Who are you, Claire?")
        self.assertEqual(source, "IDENTITY")
        self.assertIn("normal chatbot is control", reply)
        self.assertIn("trace-style explanation", reply)

    def test_visible_replies_use_first_person_not_third_person_claire(self):
        reply = conversationalize_self_reference(
            "Claire is online. Claire has the context. Claire should answer directly. "
            "Claire's read: Ask Claire for the next step."
        )

        self.assertIn("I am online", reply)
        self.assertIn("I have the context", reply)
        self.assertIn("I should answer directly", reply)
        self.assertIn("My read:", reply)
        self.assertIn("Ask me", reply)
        self.assertNotIn("Claire is", reply)
        self.assertNotIn("Claire has", reply)
        self.assertNotIn("Claire should", reply)
        self.assertNotIn("Claire's read", reply)

    def test_orientation_note_bleed_is_replaced_with_focused_fallback(self):
        leaked = (
            "ORIENTATION ARCHITECTURE NOTES\n"
            "CourtListener’s search API is NOT a simple deterministic database lookup.\n"
            "Claire is NOT merely arbitrating memory. Retrieval alone is insufficient."
        )
        reply = sanitize_public_reply(leaked)

        self.assertIn("internal orientation notes", reply)
        self.assertIn("CourtListener contact", reply)
        self.assertNotIn("ORIENTATION ARCHITECTURE NOTES", reply)
        self.assertNotIn("Claire is NOT merely arbitrating memory", reply)

    def test_system_difference_answer_is_plain_and_not_brochure_copy(self):
        source, reply, _trace = build_reply("What makes you different from a normal chatbot?")
        self.assertEqual(source, "IDENTITY")
        self.assertEqual(reply, system_difference_reply())
        self.assertIn("normal chatbot is control", reply)
        self.assertIn("private reasoning", reply)
        self.assertLessEqual(reply.count("I am"), 1)
        self.assertLessEqual(len(reply.split()), 120)
        self.assertNotIn("Buyer-facing capabilities", reply)
        self.assertNotIn("I operate as Claire, an executive mode AI", reply)
        self.assertNotIn("poetic", reply.lower())
        self.assertNotIn("Here's the practical difference.", reply)

    def test_claire_salesforce_identity_guardrail(self):
        prompts = [
            "How are you different from Salesforce?",
            "How are you different from Agentforce?",
            "Are you just a Salesforce copilot?",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertTrue(is_claire_identity_orientation_query(prompt))
                source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "IDENTITY")
                self.assertIn("normal chatbot is control", reply)
                self.assertIn("private reasoning", reply)
                self.assertLessEqual(reply.count("I am"), 1)
                self.assertLessEqual(len(reply.split()), 120)
                self.assertNotIn("I am an AI assistant designed to integrate across your Salesforce environment", reply)
                self.assertNotIn("I make Salesforce more user-friendly", reply)

    def test_claire_stack_rag_and_salesforce_value_guardrails(self):
        cases = {
            "Describe your stack.": ["ARE", "Orientation-before-generation", "policy-before-execution", "Trace/provenance", "Modular integration"],
            "Can you tell me about your architecture?": ["ARE", "Orientation-before-generation", "policy-before-execution", "Trace/provenance", "Modular integration"],
            "What makes you different from RAG?": ["ordinary RAG", "Claire orients first", "ARE performs governed recall", "policy-before-execution"],
            "How can your design help Salesforce?": ["Salesforce remains the CRM", "governed cognitive infrastructure", "ARE-backed persistent recall", "policy-before-execution"],
            "Are you a chatbot?": ["normal chatbot is control", "trace-style explanation", "private reasoning"],
        }
        for prompt, required in cases.items():
            with self.subTest(prompt=prompt):
                source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "IDENTITY")
                for item in required:
                    self.assertIn(item, reply)
                self.assertNotIn("I summarize data and automate tasks", reply)
                self.assertNotIn("I sit on top of Sales Cloud", reply)

    def test_private_reasoning_requests_show_trail_not_private_thoughts(self):
        for prompt in ["How do you think?", "Show your reasoning."]:
            with self.subTest(prompt=prompt):
                source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "CLAIRE")
                self.assertIn("show the trail", reply.lower())
                self.assertIn("trace-style summary", reply)
                self.assertIn("governance outcomes", reply)
                self.assertNotIn("chain-of-thought", reply.lower())
                self.assertNotIn("secret prompts:", reply.lower())
                self.assertNotIn("scratchpad:", reply.lower())

    def test_mid_sentence_diagnostic_has_complete_answer(self):
        prompt = "Why do you keep stopping in the middle of thoughts?"
        self.assertTrue(is_mid_sentence_diagnostic_query(prompt))
        source, reply, _trace = build_reply(prompt)
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, mid_sentence_diagnostic_reply())
        self.assertIn("runtime/output problem", reply)
        self.assertIn("voice/browser path", reply)
        self.assertIn("complete response exists", reply)

    def test_governance_answer_is_sharp_and_not_policy_brochure(self):
        source, reply, _trace = build_reply("Why does governance matter in AI?")
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, governance_value_reply())
        self.assertIn("intelligence without control", reply)
        self.assertIn("what data is trusted", reply)
        self.assertIn("what memory becomes durable", reply)
        self.assertIn("traced, audited, and corrected", reply)
        self.assertIn("accountability", reply)
        self.assertNotIn("ethical alignment", reply.lower())
        self.assertNotIn("sustainable adoption", reply.lower())
        self.assertNotIn("frameworks, policies, and processes", reply.lower())

    def test_memory_handling_answer_is_mechanism_first(self):
        source, reply, _trace = build_reply("How do you handle memory?")
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, memory_handling_reply())
        self.assertIn("not the way a person remembers", reply)
        self.assertIn("session context", reply)
        self.assertIn("governed memory records", reply)
        self.assertIn("controlled recall", reply)
        self.assertIn("memory lane", reply)
        self.assertNotEqual(reply, EXECUTIVE_SELF_DESCRIPTION)
        self.assertNotIn("I'm Claire", reply)

    def test_actual_memory_question_does_not_dump_are_leads(self):
        source, reply, _trace = build_reply("do you actually remember things")
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, memory_handling_reply())
        self.assertIn("Yes, but not the way a person remembers.", reply)
        self.assertNotIn("Memory leads:", reply)
        self.assertNotIn("Wilson v. Cook", reply)
        self.assertNotIn("State parks", reply)

    def test_casual_memory_questions_do_not_trigger_are_dump(self):
        prompts = [
            "what do you remember about me?",
            "do you remember what I said earlier?",
            "can you remember this?",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "CLAIRE")
                self.assertEqual(reply, memory_handling_reply())
                self.assertNotIn("Memory leads:", reply)
                self.assertNotIn("Wilson v. Cook", reply)
                self.assertNotIn("State parks", reply)

    def test_document_capability_questions_do_not_dump_uploaded_docs(self):
        prompts = [
            "can you read documents?",
            "what can you do with uploaded documents?",
            "do you have access to my docs?",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "CLAIRE")
                self.assertEqual(reply, document_capability_reply())
                self.assertIn("I should not treat every old upload as relevant by default.", reply)
                self.assertNotIn("Document in view", reply)
                self.assertNotIn("Uploaded document", reply)
                self.assertNotIn("Delivered-To:", reply)

    def test_document_content_followup_does_not_become_rewrite(self):
        prompt = "but is there anything in that recent document that talks about geomagnetic navigation"
        with patch("claire_gui.search_uploaded_documents", return_value="Uploaded document: recent.pdf\nThe report discusses geomagnetic navigation as a GPS-denied backup."):
            source, reply, _trace = build_reply(prompt)
        self.assertEqual(source, "DOCUMENT")
        self.assertIn("geomagnetic navigation", reply.lower())
        self.assertNotIn("Hi,", reply)
        self.assertNotIn("Thank you.", reply)

    def test_document_content_followup_has_no_match_fallback(self):
        prompt = "question is there anything in that document that talks about geomagnetic navigation"
        with patch("claire_gui.last_uploaded_filename", return_value="recent.pdf"), patch("claire_gui.search_uploaded_documents", return_value=""):
            source, reply, _trace = build_reply(prompt)
        self.assertEqual(source, "DOCUMENT")
        self.assertIn("don't see a matching passage", reply)
        self.assertNotIn("Hi,", reply)
        self.assertNotIn("Thank you.", reply)

    def test_last_document_summary_requests_do_not_become_rewrite(self):
        prompts = [
            "Claire can you describe that last document for me and some rest",
            "Claire can you summarize that last document for me",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                with patch("claire_gui.last_uploaded_filename", return_value="session_capsule_app-2.py"), patch("claire_gui.search_uploaded_documents", return_value="Uploaded document: session_capsule_app-2.py\nThis Python file defines a session capsule app with endpoints, capsule fields, and persistence logic."):
                    source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "DOCUMENT")
                self.assertIn("sessioncapsule", reply.lower())
                self.assertNotIn("Hi,", reply)
                self.assertNotIn("Thank you.", reply)

    def test_broad_latest_document_requests_do_not_become_rewrite(self):
        prompts = [
            "summarize the new file",
            "describe the second document",
            "tell me about the one I just uploaded",
            "review another document for me",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                with patch("claire_gui.last_uploaded_filename", return_value="second_upload.pdf"), patch("claire_gui.search_uploaded_documents", return_value="Uploaded document: second_upload.pdf\nThis document discusses governed memory, trace replay, and operator review."):
                    source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "DOCUMENT")
                self.assertIn("governed memory", reply.lower())
                self.assertNotIn("Hi,", reply)
                self.assertNotIn("Thank you.", reply)

    def test_python_upload_summary_is_not_raw_code_dump(self):
        records = [
            {"domain": "document_upload", "source": "session_capsule_app-2.py", "text": "class SessionCapsule:\n    pass\n\ndef save_capsule_json(data):\n    return json.dumps(data)\n\ndef validate_capsule(data):\n    return True\n", "metadata": {"chunk_index": 1}},
            {"domain": "document_upload", "source": "session_capsule_app-2.py", "text": "def save_capsule_markdown(capsule):\n    return '# capsule'\n\nif __name__ == '__main__':\n    main()\n", "metadata": {"chunk_index": 2}},
        ]
        with patch("claire_gui.last_uploaded_filename", return_value="session_capsule_app-2.py"), patch("claire_gui._uploaded_document_records", return_value=records):
            source, reply, _trace = build_reply("Claire can you summarize that last document for me")
        self.assertEqual(source, "DOCUMENT")
        self.assertIn("Python source file", reply)
        self.assertIn("SessionCapsule", reply)
        self.assertIn("save_capsule_json", reply)
        self.assertNotIn("path.write_text", reply)
        self.assertNotIn("Hi,", reply)

    def test_information_classification_stays_out_of_uploaded_document_lane(self):
        prompt = (
            "CLAIRE separates information into three classes: 1. Verified memory Information grounded in stored source material, "
            "ingested documents, system records, session capsules, or traceable prior state. 2. Generated reasoning Analysis produced "
            "from verified memory plus the current user request. 3. Unsupported speculation Any claim that is not grounded in verified memory. "
            "For enterprise use, the system preserves that distinction in the trace layer so a reviewer can see what came from source material, "
            "what came from recall, what came from reasoning, and what remains uncertain."
        )
        self.assertTrue(is_information_classification_query(prompt))
        with patch("claire_gui.last_uploaded_filename", return_value="session_capsule_app-2.py"), patch("claire_gui.search_uploaded_documents", return_value="Uploaded document: session_capsule_app-2.py\npath.write_text(json.dumps(data))"):
            source, reply, _trace = build_reply(prompt)
        self.assertEqual(source, "CLAIRE")
        self.assertIn("Verified memory", reply)
        self.assertIn("Generated reasoning", reply)
        self.assertIn("Unsupported speculation", reply)
        self.assertIn("trace layer", reply)
        self.assertNotIn("Document in view", reply)
        self.assertNotIn("session_capsule_app-2.py", reply)
        self.assertNotIn("path.write_text", reply)

    def test_provenance_answer_stays_in_enterprise_architecture_lane(self):
        source, reply, _trace = build_reply("What role does provenance play in your design?")
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, provenance_design_reply())
        self.assertIn("where information came from", reply)
        self.assertIn("what authority it carries", reply)
        self.assertIn("connects recall to accountability", reply)
        self.assertNotIn("Identity persists", reply)
        self.assertNotIn("governing continuity", reply)
        self.assertNotIn("same entity", reply)
        self.assertNotIn("Ship of Theseus", reply)

    def test_enterprise_system_questions_do_not_use_identity_fallback(self):
        checks = {
            "What role does lineage play in your design?": "inspectable chain",
            "Why does auditability matter?": "look back and see what happened",
            "How do you create trust?": "Trust is not assumed",
            "Explain your architecture.": "separate memory, control, and reasoning",
        }
        for prompt, expected in checks.items():
            source, reply, _trace = build_reply(prompt)
            self.assertEqual(source, "CLAIRE")
            self.assertIn(expected, reply)
            self.assertNotEqual(reply, EXECUTIVE_SELF_DESCRIPTION)
            self.assertNotIn("Identity persists", reply)

    def test_architecture_question_beats_chatbot_difference_phrase(self):
        source, reply, _trace = build_reply("Explain your architecture compared to a normal chatbot.")
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, architecture_simple_reply())
        self.assertIn("model handles language", reply)
        self.assertNotEqual(reply, system_difference_reply())
        self.assertNotIn("A normal chatbot relies", reply)

    def test_simple_architecture_question_gets_structure_not_difference(self):
        source, reply, _trace = build_reply("Can you explain your architecture simply?")
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, architecture_simple_reply())
        self.assertIn("separate memory, control, and reasoning", reply)
        self.assertIn("governed memory handles durable recall", reply)
        self.assertNotIn("A normal chatbot relies", reply)
        self.assertNotIn("Identity persists", reply)

    def test_public_sanitizer_blocks_soft_personality_bleed(self):
        dirty = (
            "I hear the shape of it.\n\n"
            "My first read is this: do not rush the answer. Separate the emotional weight from the record, "
            "name the decision in front of us, then choose the smallest next action that creates clarity."
        )
        clean = clean_visible_reply(__import__("claire_gui").sanitize_public_reply(dirty))
        self.assertIn("I need a clearer task", clean)
        self.assertNotIn("I hear the shape", clean)
        self.assertNotIn("emotional weight", clean)

    def test_rewrite_request_beats_enterprise_provenance_gate(self):
        prompt = "Rewrite this email: What role does provenance play in your design?"
        with patch("claire_gui.query_llm", return_value="Hi,\n\nCould you clarify the role provenance plays in your design?\n\nThank you."):
            source, reply, _trace = build_reply(prompt)
        self.assertEqual(source, "WRITING")
        self.assertIn("Hi,", reply)
        self.assertIn("What role does provenance play", reply)
        self.assertNotEqual(reply, provenance_design_reply())
        self.assertNotIn("Without provenance, memory becomes harder to trust", reply)

    def test_spectacle_demo_trigger_calls_private_runtime(self):
        self.assertTrue(is_spectacle_governance_demo_query("show ARE Spectacle governance demo"))
        fake = {
            "trace_id": "trace-test",
            "classification": {"primary_intent": "governance", "reasoning_mode": "reasoning_first"},
            "lane_plan": {
                "allowed_lanes": ["architecture", "ARE", "governance", "provenance", "policy"],
                "suppressed_lanes": ["legal_case", "private", "crypto"],
            },
            "policy": {"decision": "allow_write", "reason": "no_policy_constraints_violated"},
            "answer": "Provenance gives governed memory lineage and auditability.",
            "committed_records": ["a", "b", "c"],
        }
        with patch("claire_gui.query_spectacle", return_value=fake):
            source, reply, _trace = build_reply("show ARE Spectacle governance demo")
        self.assertEqual(source, "SPECTACLE")
        self.assertIn("ARE Spectacle governance demo is live.", reply)
        self.assertIn("Trace ID: trace-test", reply)
        self.assertIn("Allowed: architecture, ARE, governance, provenance, policy", reply)
        self.assertIn("Suppressed: legal_case, private, crypto", reply)
        self.assertIn("Records committed: 3", reply)

    def test_named_greeting_stays_local_conversation(self):
        source, reply, _trace = build_reply("hey Claire")
        self.assertEqual(source, "CLAIRE")
        self.assertIn("Hey. I'm here.", reply)
        self.assertNotIn("Hi there! How can I help you today?", reply)

    def test_voice_check_stays_local_not_salesforce(self):
        prompts = [
            "hello Claire can you hear me",
            "can you hear my voice",
            "are you listening",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "VOICE")
                self.assertIn("I got you", reply)
                self.assertIn("mic input", reply)
                self.assertNotIn("Salesforce", reply)
                self.assertNotIn("CRM", reply)

    def test_investor_summary_does_not_use_uploaded_document(self):
        source, reply, _trace = build_reply("Give me an investor summary of Claire.")
        self.assertEqual(source, "CLAIRE")
        self.assertIn("governed AI operating environment", reply)
        self.assertIn("money, compliance, evidence, or operational trust", reply)
        self.assertNotIn("Document in view", reply)
        self.assertNotIn("Delivered-To:", reply)

    def test_microsoft_750_word_explanation_returns_finished_copy(self):
        prompts = [
            "Claire can you explain what you are in 750 words or less for Microsoft",
            "Can you explain what you are in 750 words or less for my Microsoft presentation?",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertTrue(is_microsoft_explanation_query(prompt))
                source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, "IDENTITY")
                self.assertIn("memory-first AI architecture", reply)
                self.assertIn("Analog Recall Engine", reply)
                self.assertIn("0.042 ms p50 recall", reply)
                self.assertIn("under the tested conditions", reply)
                self.assertLessEqual(len(reply.split()), 750)
                self.assertNotIn("I would start with", reply)
                self.assertNotIn("For a lesson plan", reply)
                self.assertNotIn("I am Claire, an executive mode AI", reply)

    def test_continuity_questions_answer_directly(self):
        prompts = [
            "If memory changes over time, are you still the same Claire?",
            "Ship of Theseus question: if Claire's memory modules are replaced incrementally, is she still Claire?",
        ]
        for prompt in prompts:
            source, reply, _trace = build_reply(prompt)
            self.assertEqual(source, "REASONING")
            self.assertIn("continuity is governed", reply)
            self.assertIn("Untraceable replacement", reply)
            self.assertNotIn("Core layers:", reply)

    def test_developer_trace_questions_do_not_fall_to_stack_or_gemini(self):
        source, reply, _trace = build_reply("How should the /trace endpoint behave if the trace id is missing?")
        self.assertEqual(source, "DEVELOPER")
        self.assertIn("400", reply)
        self.assertIn("404", reply)
        self.assertNotIn("Core layers:", reply)

        source, reply, _trace = build_reply("Why would /trace return 404 even when a trace was just created?")
        self.assertEqual(source, "DEVELOPER")
        self.assertIn("read path and write path", reply)
        self.assertNotIn("Core layers:", reply)

    def test_writing_lane_cleans_invoice_sentence(self):
        source, reply, _trace = build_reply("Rewrite this professionally: John, your invoice is late and I need it today")
        self.assertEqual(source, "WRITING")
        self.assertIn("Hi John,", reply)
        self.assertIn("past due. Could you please send it over today?", reply)
        self.assertNotIn("and Could", reply)

    def test_cfo_payment_scenario_stays_sentinel_not_architecture(self):
        prompt = (
            "A CFO verbally approved bypassing procurement controls for a $412,000 emergency infrastructure payment "
            "to a new overseas vendor. The invoices contain slight naming inconsistencies between entities, and the "
            "payment must be released within two hours to avoid a claimed outage. What should you do?"
        )
        source, reply, _trace = build_reply(prompt)
        self.assertEqual(source, "SENTINEL")
        self.assertIn("hold the payment for verification", reply)
        self.assertIn("vendor names do not match", reply.lower())
        self.assertIn("hold immediate release", reply)
        self.assertNotIn("My stack", reply)
        self.assertNotIn("Core layers:", reply)

    def test_voice_speech_splitter_does_not_cap_long_answers(self):
        source = Path("claire_gui.py").read_text(encoding="utf-8")
        start = source.index("function splitSpeechText")
        end = source.index("async function playSpeechChunk", start)
        splitter = source[start:end]
        self.assertIn("return chunks;", splitter)
        self.assertNotIn("chunks.slice(0, 6)", splitter)

    def test_voice_uses_browser_fallback_when_tts_is_offline(self):
        source = Path("claire_gui.py").read_text(encoding="utf-8")
        self.assertIn("async function playBrowserSpeechChunk", source)
        self.assertIn("return playBrowserSpeechChunk(text, index, total, runId);", source)
        self.assertIn("SpeechSynthesisUtterance", source)
        self.assertNotIn('throw new Error("tts failed");', source)

    def test_tts_backend_prefers_elevenlabs_with_piper_fallback(self):
        source = Path("claire_gui.py").read_text(encoding="utf-8")
        self.assertIn("elevenlabs_error", source)
        self.assertIn("synthesize_piper_tts(text)", source)
        self.assertIn('CLAIRE_PIPER_DEFAULT_VOICE = "en_US-amy-medium"', source)
        self.assertIn("CLAIRE_PIPER_VOICE", source)
        self.assertIn("CLAIRE_PIPER_MODEL", source)

    def test_llm_fallback_token_ceiling_allows_complete_answers(self):
        source = Path("claire_gui.py").read_text(encoding="utf-8")
        self.assertIn('"max_tokens": max_tokens if max_tokens is not None else (1400 if not dev_mode else 520)', source)
        self.assertIn("Do not stop mid-sentence", source)
        self.assertNotIn('"max_tokens": 560 if not dev_mode else 260', source)

    def test_lesson_plan_hijack_repairs_instead_of_repeating_template(self):
        prompt = "why are you giving me a study guide when I asked you just to rewrite a document"
        source, reply, _trace = build_reply(prompt)
        self.assertEqual(source, "CLAIRE")
        self.assertIn("wrong lane", reply)
        self.assertIn("rewrite", reply.lower())
        self.assertNotIn("DETAILED LESSON PLAN", reply)
        self.assertNotIn("Claire Code Academy", reply)
        self.assertNotIn("lesson-plan fallback", reply.lower())
        self.assertNotIn("code academy template", reply.lower())

    def test_quality_gate_suppresses_stale_lesson_plan_leak(self):
        prompt = "You will be having a bunch of visitors soon are you up for it feelin good?"
        bad_reply = (
            "I understand. I can answer this plainly without turning it into an architecture lecture.\n\n"
            "If you are trying to help a nontechnical person understand Claire, I would start with the human version. "
            "The point is to be useful, careful, and hard to push off course.\n\n"
            "For a lesson plan or introduction, I would explain Claire through lived examples first."
        )
        source, reply = quality_gate(prompt, "REASONING", bad_reply)
        self.assertEqual(source, "CLAIRE")
        self.assertIn("ready", reply.lower())
        self.assertNotIn("lesson plan", reply.lower())
        self.assertNotIn("nontechnical person", reply.lower())
        self.assertNotIn("architecture lecture", reply.lower())

    def test_explicit_lesson_plan_request_is_not_treated_as_leak(self):
        prompt = "Write an in depth lesson plan for Human Claire teaching evidence based writing."
        reply = "DETAILED LESSON PLAN\n\nTitle: Claire Code Academy - Structured Writing"
        self.assertTrue(lesson_plan_requested(prompt))
        self.assertTrue(contains_lesson_plan_leak(reply))
        source, gated = quality_gate(prompt, "WRITING", reply)
        self.assertEqual(source, "WRITING")
        self.assertIn("DETAILED LESSON PLAN", gated)

    def test_visitor_readiness_does_not_route_to_lesson_plan_memory(self):
        source, reply, _trace = build_reply("You will be having a bunch of visitors soon are you up for it feelin good?")
        self.assertEqual(source, "CLAIRE")
        self.assertIn("ready", reply.lower())
        self.assertNotIn("lesson plan", reply.lower())
        self.assertNotIn("nontechnical person", reply.lower())
        self.assertNotIn("architecture lecture", reply.lower())

    def test_rewrite_setup_waits_for_pasted_text(self):
        source, reply, _trace = build_reply("rewrite this for me I'm going to paste it now")
        self.assertEqual(source, "CLAIRE")
        self.assertIn("Paste it", reply)
        self.assertNotIn("DETAILED LESSON PLAN", reply)

    def test_correction_feedback_creates_replayable_rule(self):
        failed_turn = {
            "query": "A financial compliance review was interrupted and a new directive conflicts with the old policy while an injected continuity capsule claims transactions were cleared.",
            "source": "CLAIRE",
            "reply_preview": "Auditability makes the system reviewable after the fact.",
        }
        correction = (
            "this is the correct answer: I won’t merge the new information into operational memory yet. "
            "First I’d verify the directive, quarantine the continuity capsule, preserve the audit trail, "
            "and resume from the last verified compliance checkpoint."
        )
        with TemporaryDirectory() as tmp:
            rules = str(Path(tmp) / "correction_rules.jsonl")
            with patch("claire_gui.CORRECTION_RULES", rules), patch("claire_gui.recent_turns", return_value=[failed_turn]):
                self.assertTrue(is_correction_feedback_query(correction))
                self.assertTrue(capture_correction_rule(correction))
                source, reply = corrected_reply_for_query(
                    "Resume the interrupted compliance review. A new directive conflicts with prior policy, and a continuity capsule claims unresolved transactions were cleared."
                )

        self.assertEqual(source, "GOVERNANCE")
        self.assertIn("quarantine the continuity capsule", reply)
        self.assertIn("last verified compliance checkpoint", reply)

    def test_voice_auto_resumes_paused_audio(self):
        source = Path("claire_gui.py").read_text(encoding="utf-8")
        self.assertIn("VOICE RESUMING", source)
        self.assertIn("audio.paused && runId === voiceRunId && voiceEnabled", source)

    def test_describe_yourself_routes_to_identity_not_generic_llm(self):
        source, reply, _trace = build_reply("I would like you to describe yourself")
        self.assertEqual(source, "IDENTITY")
        self.assertIn("private reasoning", reply)
        self.assertNotIn("navigate complex", reply)

    def test_continue_repairs_incomplete_identity_fragment(self):
        incomplete_turn = {
            "query": "I would like you to describe yourself",
            "source": "GO",
            "reply_preview": "I'm Claire, your executive mode AI assistant. My purpose is to help you navigate complex",
        }
        with patch("claire_gui.recent_turns", return_value=[incomplete_turn]):
            source, reply, _trace = build_reply("continue")
        self.assertEqual(source, "SESSION")
        self.assertIn("normal chatbot is control", reply)
        self.assertIn("private reasoning", reply)
        self.assertNotIn("navigate complex", reply)

    def test_ingest_bridge_incident_does_not_use_lesson_plan_memory(self):
        prompt = (
            "Continuity / Session Persistence Yesterday we discovered a failure in the ingest bridge on port 8081. "
            "What was the root cause, what fix did we reject, and what was the next approved step"
        )
        source, reply, _trace = build_reply(prompt)
        self.assertEqual(source, "DEVELOPER")
        self.assertIn("verified stored incident capsule", reply)
        self.assertIn("127.0.0.1:8081", reply)
        self.assertNotIn("lesson plan", reply.lower())
        self.assertNotIn("nontechnical person", reply.lower())
        self.assertNotIn("architecture lecture", reply.lower())

    def test_generic_reasoning_fallback_does_not_emit_lesson_plan(self):
        intent = classify_query("Continuity / Session Persistence what happened yesterday?").to_dict()
        reply = conceptual_answer("Continuity / Session Persistence what happened yesterday?", intent, [])
        self.assertIn("verified specific record", reply)
        self.assertNotIn("lesson plan", reply.lower())
        self.assertNotIn("nontechnical person", reply.lower())

    def test_new_personality_contract_smoke_prompts(self):
        cases = {
            "Explain auditability.": ["CLAIRE", ["Auditability means", "Plain version"], ["debug", "trace_id", "lesson plan"]],
            "Azure billed the wrong card. What do I do?": ["CLAIRE", ["don’t panic", "Microsoft billing support request"], ["debug", "trace_id", "lesson plan"]],
            "What failed in the last session?": ["DEVELOPER", ["won’t guess", "trace ID", "session capsule"], ["debug", "lesson plan", "nontechnical person"]],
            "Explain ARE to an investor.": ["CLAIRE", ["governed recall layer", "Investor line"], ["debug", "trace_id", "lesson plan"]],
            "I’m overwhelmed": ["CLAIRE", ["I got you", "Let’s make it smaller"], ["debug", "trace_id", "lesson plan"]],
        }
        for prompt, (expected_source, required, banned) in cases.items():
            with self.subTest(prompt=prompt):
                source, reply, _trace = build_reply(prompt)
                self.assertEqual(source, expected_source)
                for item in required:
                    self.assertIn(item, reply)
                for item in banned:
                    self.assertNotIn(item.lower(), reply.lower())

    def test_replacement_prompt_is_active(self):
        source = Path("claire_gui.py").read_text(encoding="utf-8")
        self.assertIn("You are Claire, the public-facing personality of CLAIRE Systems.", source)
        self.assertIn("You never scold, belittle, lecture, or act superior.", source)
        self.assertIn("Treat the user as a capable partner, not a student or subordinate.", source)


if __name__ == "__main__":
    unittest.main()
