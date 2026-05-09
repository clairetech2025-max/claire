import unittest
from unittest.mock import patch

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
    governance_value_reply,
    memory_handling_reply,
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
        self.assertIn("governed AI operating environment", visible)
        self.assertIn("auditable output", visible)
        self.assertIn("provenance", visible.lower())
        self.assertIn("Do not use poetic, mystical, therapeutic", EXECUTIVE_SYSTEM_PROMPT)
        for term in EXECUTIVE_BANNED_TERMS:
            self.assertNotIn(term.lower(), visible.lower())

    def test_public_identity_query_returns_executive_intro(self):
        source, reply, _trace = build_reply("Who are you, Claire?")
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, EXECUTIVE_SELF_DESCRIPTION)

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

    def test_system_difference_answer_is_sharp_and_not_brochure_copy(self):
        source, reply, _trace = build_reply("What makes you different from a normal chatbot?")
        self.assertEqual(source, "CLAIRE")
        self.assertEqual(reply, system_difference_reply())
        self.assertIn("transient model context", reply)
        self.assertIn("governed memory", reply)
        self.assertIn("traceable reasoning", reply)
        self.assertIn("bounded behavior", reply)
        self.assertNotIn("Buyer-facing capabilities", reply)
        self.assertNotIn("I operate as Claire, an executive mode AI", reply)
        self.assertNotIn("poetic", reply.lower())

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
        self.assertIn("controlled external layer", reply)
        self.assertIn("stored, recalled, and used under governance rules", reply)
        self.assertIn("traceability", reply)
        self.assertIn("bounded access", reply)
        self.assertIn("model-only approach", reply)
        self.assertNotEqual(reply, EXECUTIVE_SELF_DESCRIPTION)
        self.assertNotIn("I'm Claire", reply)

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
            "Why does auditability matter?": "reviewable after the fact",
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


if __name__ == "__main__":
    unittest.main()
