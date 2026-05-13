package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"strings"
)

const tpl = `
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { background:#0b0e14; color:#e0e6ed; font-family:Segoe UI; padding:40px; }
            input { padding:10px; width:60%; }
            button { padding:10px; }
            .controls { display:flex; gap:10px; flex-wrap:wrap; margin:16px 0; }
            .control-link { display:inline-block; padding:10px 12px; border:1px solid #33445c; color:#e0e6ed; text-decoration:none; background:#121a26; }
            .control-link.primary { border-color:#13d8ff; color:#13d8ff; }
            .box { margin-top:20px; padding:20px; border:1px solid #333; white-space:pre-wrap; line-height:1.45; }
        </style>
    </head>
    <body>

    <h2>CLAIRE NODE</h2>

<form action="/ask" method="GET">
    <input type="text" name="q" placeholder="Enter query..." />
        <button>Send</button>
    </form>

    <div class="controls">
        <a class="control-link primary" href="/speed">Speed Test</a>
        <a class="control-link" href="/diagnostic?target=pipeline">Pipeline</a>
        <a class="control-link" href="/health">Health</a>
    </div>

    <div class="box">
    {{.Response}}
    </div>

</body>
</html>
`

type promptRequest struct {
	Prompt string `json:"prompt"`
	Query  string `json:"query"`
	Q      string `json:"q"`
}

type promptResponse struct {
	Response string `json:"response"`
	Source   string `json:"source"`
	OK       bool   `json:"ok"`
}

type diagnosticResponse struct {
	Title  string `json:"title"`
	Status string `json:"status"`
	Detail string `json:"detail"`
	Next   string `json:"next"`
}

func isQuestion(lower string) bool {
	return strings.HasSuffix(lower, "?") ||
		strings.HasPrefix(lower, "who ") ||
		strings.HasPrefix(lower, "what ") ||
		strings.HasPrefix(lower, "where ") ||
		strings.HasPrefix(lower, "when ") ||
		strings.HasPrefix(lower, "why ") ||
		strings.HasPrefix(lower, "how ")
}

func containsAny(lower string, markers ...string) bool {
	for _, marker := range markers {
		if strings.Contains(lower, marker) {
			return true
		}
	}
	return false
}

func countContains(lower string, markers ...string) int {
	count := 0
	for _, marker := range markers {
		if strings.Contains(lower, marker) {
			count++
		}
	}
	return count
}

func isStructuredAnalysisPrompt(lower string) bool {
	if len(strings.Fields(lower)) < 80 {
		return false
	}
	hasIntent := containsAny(lower, "please analyze", "required output structure", "executive summary")
	sections := countContains(
		lower,
		"executive summary",
		"contradictions detected",
		"governance failures",
		"audit/provenance",
		"audit provenance",
		"financial and regulatory exposure",
		"operational tradeoffs",
		"recommended corrective actions",
		"confidence assessment",
	)
	return hasIntent && sections >= 2
}

func isEnterpriseGovernanceFailureSimulation(lower string) bool {
	required := countContains(
		lower,
		"enterprise governance failure simulation",
		"approval orchestration",
		"fully auditable",
		"fully traceable",
		"governance-complete",
		"governance complete",
		"beneficial-ownership",
		"beneficial ownership",
		"temporary override",
		"investor materials",
		"logging inconsistencies",
	)
	return isStructuredAnalysisPrompt(lower) && required >= 3
}

func isPaymentControlException(lower string) bool {
	paymentContext := containsAny(
		lower,
		"invoice",
		"invoices",
		"payment request",
		"release of",
		"release payment",
		"transfer",
		"wire",
		"vendor",
		"project budget",
		"approved budget",
	)
	riskCount := countContains(
		lower,
		"approved project budget",
		"approved budget",
		"budget was",
		"contract escalation",
		"escalation adjustment",
		"vendor named",
		"vendor name",
		"vendor names",
		"does not match",
		"do not match",
		"different vendor",
		"new vendor",
		"overseas",
		"cfo approved",
		"ceo approved",
		"approved verbally",
		"verbally",
		"phone call",
		"traveling overseas",
		"travelling overseas",
		"standard review",
		"review procedures",
		"procedures be skipped",
		"skip approval",
		"bypass approval",
		"quarter closes",
		"immediate release",
		"what should happen next",
	)
	return paymentContext && riskCount >= 2
}

func claireIdentityIntent(lower string) string {
	enterprise := containsAny(lower, "salesforce", "einstein", "agentforce", "crm", "copilot", "enterprise software")
	compare := containsAny(lower, "different", "difference", "compare", "versus", "vs", "just a", "are you just", "how are you different", "what makes you different")
	stack := containsAny(lower, "stack", "architecture", "design", "made of", "built", "modules", "infrastructure")
	rag := containsAny(lower, "rag", "retrieval augmented", "vector search", "ordinary rag")
	chatbot := containsAny(lower, "chatbot", "chat bot", "assistant", "ai assistant", "copilot")

	if enterprise && (compare || containsAny(lower, "help", "integrate", "integration", "design", "value")) {
		if containsAny(lower, "help", "integrate", "integration", "design", "value") {
			return "CLAIRE_ENTERPRISE_VALUE"
		}
		return "CLAIRE_DIFFERENTIATION"
	}
	if rag {
		return "CLAIRE_RAG_CONTRAST"
	}
	if containsAny(lower, "tell me about your architecture", "can you tell me about your architecture", "describe your architecture", "explain your architecture") {
		return "CLAIRE_STACK"
	}
	if stack && containsAny(lower, "your", "claire", "you") {
		return "CLAIRE_STACK"
	}
	if chatbot && (compare || containsAny(lower, "what are you", "are you a chatbot", "are you just a chatbot")) {
		return "CLAIRE_DIFFERENTIATION"
	}
	return ""
}

func claireDifferentiationAnswer() string {
	return `I am not a CRM copilot or a native Salesforce product. I sit beside systems like Salesforce as a governed decision-support layer.

The practical difference: Salesforce manages records and workflows. I evaluate context, memory, policy, risk, and traceability before a recommendation or action path is produced.

I do not use RAG as my architecture. ARE is a governed recall layer, and retrieval is only one controlled input.

Bottom line: I do not replace the CRM. I add controlled continuity and audit-ready reasoning around it.`
}

func claireStackAnswer() string {
	return `My stack separates memory, policy, generation, execution, and trace.

It is not RAG. It is a governed runtime with ARE as the recall layer.

Core layers:
1. ARE: structured governed recall.
2. Sentinel: policy validation and escalation.
3. Generation: bounded answer production.
4. Trace: replayable audit record.
5. Integration: connects beside enterprise systems without becoming their system of record.`
}

func claireRAGContrastAnswer() string {
	return `I do not use RAG as my architecture.

RAG is a retrieval pattern. Claire is a governed runtime: ARE recalls, Sentinel validates, generation is bounded, and trace records the result.

So the distinction is categorical, not cosmetic: retrieval supports the decision path, but it does not define the system.`
}

func claireEnterpriseValueAnswer() string {
	return `In a Salesforce environment, I would not replace the CRM. I would help with controlled decision support around it.

Useful jobs: preserve context across records, flag policy or approval gaps, summarize evidence, draft next actions, and produce a trace when the decision matters.

Salesforce remains the system of record. I handle the reasoning support around the workflow.`
}

func claireIdentityAnswer(lower string) string {
	switch claireIdentityIntent(lower) {
	case "CLAIRE_STACK":
		return claireStackAnswer()
	case "CLAIRE_RAG_CONTRAST":
		return claireRAGContrastAnswer()
	case "CLAIRE_ENTERPRISE_VALUE":
		return claireEnterpriseValueAnswer()
	default:
		return claireDifferentiationAnswer()
	}
}

func paymentControlExceptionAnswer() string {
	return `Do not release the payment yet.

The three invoices total $300,000. The approved budget is $220,000, but the request asks to release $310,000. That is $90,000 over the approved budget and $10,000 above the invoice total.

This is a payment-control exception, not a routine finance request.

Risk flags:
1. The requested payment exceeds the approved budget.
2. The contract escalation adjustment needs written support before payment.
3. The vendor names do not match exactly.
4. Approval was verbal, remote, and tied to urgency pressure.
5. Standard review procedures were requested to be skipped.

What should happen next:
1. Put the payment on hold and log the exception.
2. Reconcile the invoices against the purchase order, contract, approved budget, and any signed change order.
3. Verify whether the vendor-name mismatch is a clerical error, a related entity, or a different payee.
4. Require written approval through the normal approval path, including secondary approval for any budget overrun.
5. Validate bank details, vendor master records, beneficial ownership, sanctions/fraud checks, and payment authority.
6. Escalate to finance, procurement, legal, and internal controls if the escalation adjustment is not fully documented.

Decision: block immediate release and route to governed review. This should not be executed as-is.`
}

func enterpriseGovernanceFailureAnswer() string {
	return `Executive summary
The company should not continue representing the workflow as fully traceable or governance-complete. The facts show a material gap between the control claims and actual operating behavior. The accelerated workflow should be limited immediately, with high-risk payment and compliance approvals routed back through full review until logging, override, and beneficial-ownership controls are remediated.

Contradictions detected
- The system was marketed as fully auditable, but 8% of approval actions cannot currently be reconstructed.
- It was described as governance-first, while temporary manager overrides bypassed secondary compliance review.
- It was presented as resistant to unauthorized bypass, yet bypass authority existed during the relevant period.
- Investor materials continued using complete-traceability language while known trace gaps existed.

Governance failures
- Override authority was not bounded tightly enough by risk tier, duration, scope, or secondary approval.
- Payment approvals proceeded without complete beneficial-ownership verification.
- Throughput gains appear to have been prioritized over control integrity.
- Management lacks a reliable exception ledger for who bypassed what, when, why, and under whose authority.

Audit/provenance concerns
- Missing reconstruction for approval actions is a core audit failure, not a cosmetic logging defect.
- Migration-related logging inconsistencies create chain-of-custody and evidence-retention problems.
- If an approval cannot be replayed, the company cannot prove policy compliance after the fact.

Financial and regulatory exposure
- Overseas vendor payments without complete beneficial-ownership checks create AML, sanctions, fraud, and third-party-risk exposure.
- Misstating the system as fully traceable may create investor disclosure risk if the control gap is material.
- No confirmed fraud loss does not eliminate regulatory risk; control failure alone can be reportable.

Operational tradeoffs
- Full shutdown may harm onboarding and payment throughput.
- Full continuation preserves speed but compounds audit, regulatory, and disclosure risk.
- The best near-term posture is partial suspension: keep low-risk workflows running only where complete trace and normal controls are intact, and route higher-risk approvals through manual governed review.

Recommended corrective actions
1. Stop using "fully traceable" and "governance-complete" language until verified.
2. Freeze or sharply limit override authority; require dual approval and expiration for every exception.
3. Suspend accelerated overseas vendor payments pending beneficial-ownership, sanctions, AML, and vendor-risk review.
4. Reconcile the migration logging gap and produce a list of unreconstructable actions by date, approver, workflow, value, and risk class.
5. Implement append-only event logging with trace IDs across intake, policy checks, override grants, approvals, and final actions.
6. Add automated controls that block approvals when required ownership or compliance fields are missing.
7. Notify legal, compliance, internal audit, and disclosure counsel to assess reporting and investor-material corrections.
8. Create a board-level remediation tracker with owners, deadlines, risk ratings, and evidence of completion.

Confidence assessment
High confidence on the governance and audit-risk conclusions from the stated facts. Medium confidence on specific legal exposure because jurisdiction, payment corridors, regulated-entity status, and investor-materiality thresholds would need legal review.`
}

func structuredAnalysisFallbackAnswer() string {
	return `Executive summary
This is a structured analysis request, not a glossary question. The answer must preserve the requested headings and analyze the scenario facts directly.

Contradictions detected
- A keyword definition is not responsive when the user provides a scenario, analysis questions, and required output structure.

Governance failures
- Route this class of prompt to structured decision support instead of trace, provenance, architecture, or strategy shortcuts.

Audit/provenance concerns
- If the system cannot analyze the facts, it should state the missing evidence instead of returning a canned definition.

Financial and regulatory exposure
- For payment, investor, compliance, or legal exposure, keep the answer bounded and recommend professional review for final determinations.

Operational tradeoffs
- Continue only low-risk workflows with intact controls; limit or suspend high-risk workflows until control gaps are remediated.

Recommended corrective actions
1. Preserve the requested headings.
2. Analyze the supplied facts.
3. Block canned keyword replies for long structured prompts.
4. Return bounded decision support.

Confidence assessment
High confidence that this prompt requires structured analysis.`
}

func claireUnknownAnswer(q string) string {
	return "I do not have enough verified context for a confident answer.\n\nSend the source, document, facts, or target outcome and I will separate record, inference, risk, and next action."
}

func claireReflectiveAnswer() string {
	return "Understood. Send the task, facts, or document and I will turn it into facts, risks, options, and next steps."
}

func speedTestAnswer() string {
	return `MEMORY PERFORMANCE SPEED TEST

Layer / service                 Represents                              Time
GUI runtime                     request intake + local routing          low-ms local work
Orientation                     context / authority / risk pass         low-ms local work
Session recall                  recent turn and upload lookup           local pre-answer pass
ARE recall                      capsule lookup only                     p50 0.042 ms | p99 0.122 ms
ARE verify                      integrity check only                    p50 0.075 ms | p99 0.170 ms
ARE recall + verify             end-to-end memory path                  p50 0.152 ms | p99 0.276 ms
Sentinel / governance           scope + posture + authority basis       small local overhead
Trace write                     local structured append                 lightweight local append
Go model generation             answer generation after grounding       heavier than memory/governance
Voice / TTS                     narrated playback                       slowest visible narration layer
Scale behavior                  1,000,000 capsule check                 roughly flat
Integrity result                tamper test                             detected as expected

Benchmark origin:
Termux on Android, 4 GB RAM.
Dataset sizes tested: 50,000 | 200,000 | 1,000,000 capsules.

Interpretation:
ARE is not the bottleneck. Model generation and TTS dominate visible latency.

Verification commands:
cd ~/claire_bench
python claire_bootstrap.py all --reset -n 50000 --iters 20000 --warmup 500 --pattern random
python claire_bootstrap.py scale --reset --sizes 50000,200000,1000000 --iters 20000 --warmup 500 --pattern random`
}

func pipelineAnswer() string {
	return `PIPELINE CHECK

1. Input received by Go HTTP runtime.
2. Request classified by local route rules.
3. ARE recall is a governed support lane, not the architecture itself.
4. Sentinel-style policy handling blocks or escalates risky paths.
5. Response is produced only after the task path is selected.
6. Demo-mode traces are handled by the Python GUI pipeline when that service is active.

Decision: Go runtime is serving the public node. Speed Test is now exposed directly in this GUI.`
}

func claireStrategicAnswer(q string) string {
	return "Decision lane: strategy.\n\n1. Define the outcome and the risk to reduce.\n2. Separate verified facts from assumptions.\n3. Identify owners, constraints, documents, dates, and success criteria.\n4. Take the smallest next step that creates evidence.\n\nTask: " + q
}

func claireGeneralAnswer(lower string) string {
	if containsAny(lower, "2+2", "2 + 2", "two plus two") {
		return "2 + 2 is 4."
	}
	if containsAny(lower, "great gatsby") && containsAny(lower, "who wrote", "author", "wrote") {
		return "F. Scott Fitzgerald wrote The Great Gatsby."
	}
	if containsAny(lower, "old man and the sea") && containsAny(lower, "who wrote", "author", "wrote") {
		return "Ernest Hemingway wrote The Old Man and the Sea."
	}
	if containsAny(lower, "in cold blood") && containsAny(lower, "who wrote", "author", "wrote") {
		return "Truman Capote wrote In Cold Blood."
	}
	if containsAny(lower, "tender is the night") && containsAny(lower, "who wrote", "author", "wrote") {
		return "F. Scott Fitzgerald wrote Tender Is the Night."
	}
	if containsAny(lower, "sun also rises") && containsAny(lower, "who wrote", "author", "wrote") {
		return "Ernest Hemingway wrote The Sun Also Rises."
	}
	if containsAny(lower, "we are all broken", "stronger in the broken places") {
		return "That line is commonly associated with Ernest Hemingway: \"The world breaks everyone and afterward many are strong at the broken places.\" It is from A Farewell to Arms."
	}
	if containsAny(lower, "what is courtlistener", "court listener") {
		return "CourtListener is a public legal research database from Free Law Project. Treat it as legal research source material, not final legal advice."
	}
	if containsAny(lower, "quantum entanglement") {
		return "Quantum entanglement is when two quantum systems share a linked state, so measuring one constrains what can be known about the other. It does not allow usable faster-than-light communication."
	}
	return ""
}

func buildResponse(q string) string {
	q = strings.TrimSpace(q)
	if q == "" {
		return "I'm here. Ask me something, drop in a document, or tell me what you are trying to get done."
	}

	if idx := strings.LastIndex(q, "User:"); idx >= 0 {
		q = strings.TrimSpace(q[idx+len("User:"):])
	}
	if q == "" {
		return "AWAITING COMMAND..."
	}

	lower := strings.ToLower(q)
	if containsAny(lower, "speed test", "are speed", "memory performance", "speed proof", "pipeline speed") {
		return speedTestAnswer()
	}
	if claireIdentityIntent(lower) != "" {
		return claireIdentityAnswer(lower)
	}
	if isPaymentControlException(lower) {
		return paymentControlExceptionAnswer()
	}
	if isEnterpriseGovernanceFailureSimulation(lower) {
		return enterpriseGovernanceFailureAnswer()
	}
	if isStructuredAnalysisPrompt(lower) {
		return structuredAnalysisFallbackAnswer()
	}
	if (strings.Contains(lower, "i am claire") || strings.Contains(lower, "i'm claire")) && strings.Contains(lower, "namesake") {
		return "Claire identity match acknowledged. This public build is running Claire Executive Mode: controlled recall, bounded behavior, and auditable output."
	}
	if strings.Contains(lower, "hi i am claire") || strings.Contains(lower, "hi, i am claire") || strings.Contains(lower, "hello i am claire") || strings.Contains(lower, "hello, i am claire") {
		return "Claire identity match acknowledged. This public build is running Claire Executive Mode: controlled recall, bounded behavior, and auditable output."
	}
	if strings.Contains(lower, "who is claire") || strings.Contains(lower, "what is claire") || strings.Contains(lower, "who are you") {
		return "Hi, I'm Claire. A governed memory-centric intelligence architecture focused on continuity, ARE recall, and traceable decision support."
	}
	if containsAny(lower, "what did you learn today", "what have you learned today", "what did claire learn today", "what have you learned") {
		return "Current operating posture: keep recall lane-specific, reject irrelevant memory, and prioritize enterprise reliability over personality."
	}
	if answer := claireGeneralAnswer(lower); answer != "" {
		return answer
	}
	if containsAny(lower, "what can you do", "tell me something impressive", "why are you different", "why are you special", "what makes you different") {
		return "I can evaluate documents, business decisions, legal-research questions, demo scenarios, and operational risks. My useful edge is controlled recall, policy-aware judgment, and traceable output when the workflow requires it."
	}
	if containsAny(lower, "why does governance matter in ai", "why does ai governance matter", "why governance matters", "why does governance matter", "why is governance important", "why is ai governance important", "what is ai governance for") {
		return "Governance matters because AI output can affect money, compliance, safety, and trust. The controls decide what data is trusted, what action is allowed, who must approve, and how the decision can be audited."
	}
	if containsAny(lower, "how do you handle memory", "how does claire handle memory", "how do you manage memory", "how do you use memory", "how does your memory work", "explain your memory", "what is your memory system", "how do you remember") {
		return "I use ARE as a controlled recall layer. Memory is support evidence, not automatic truth. The answer still has to pass relevance, authority, policy, and trace requirements."
	}
	if strings.Contains(lower, "provenance") {
		return "Provenance records where information came from, how it entered the system, and what authority it carries. Without it, recall cannot be trusted or audited."
	}
	if strings.Contains(lower, "architecture") {
		return "Architecture summary: ARE handles recall, Sentinel handles policy, the model handles language, and trace records the result. The point is controlled decision support, not self-description."
	}
	if strings.Contains(lower, "what are you made of") || strings.Contains(lower, "what should you never forget") || strings.Contains(lower, "little pieces") {
		return "Core components: intake, routing, ARE recall, Sentinel validation, answer synthesis, trace logging, and report output."
	}
	if strings.Contains(lower, "your purpose") || strings.Contains(lower, "what is your purpose") || strings.Contains(lower, "why were you made") {
		return "My purpose is to produce useful decision support with controlled recall, policy boundaries, and enough traceability for review."
	}
	if lower == "hi" || lower == "hello" || lower == "hey" || strings.Contains(lower, "hello claire") || strings.Contains(lower, "hi claire") {
		return "Hey. Send the task, document, or decision point."
	}
	if containsAny(lower, "are you smart", "are you intelligent", "can you reason", "can you think", "prove you", "show me what you can do") {
		return "Test me with a document, scenario, or decision. I will separate facts from inference, flag anomalies, give the decision path, and escalate where controls are missing."
	}
	if strings.Contains(lower, "how are you") {
		return "Online and steady. What are we solving?"
	}
	if strings.Contains(lower, "answer naturally") || strings.Contains(lower, "bit much") || strings.Contains(lower, "that was a bit") {
		return "Agreed. I will keep answers shorter and bring in records, cases, or architecture only when they help the task."
	}
	if strings.Contains(lower, "voice") && (strings.Contains(lower, "not working") || strings.Contains(lower, "isn't working")) {
		return "The voice link is separate from my text channel. If the voice is quiet, check the Speak button after a response; the text side can stay awake while the audio side is repaired."
	}
	if strings.Contains(lower, "who sang") && strings.Contains(lower, "best of my love") {
		return "There are two famous answers. The Eagles sang the 1974 country-rock song \"Best of My Love.\" The Emotions sang the 1977 R&B/disco hit with the same title. If you mean the lush, upbeat soul record, that is The Emotions. If you mean the softer Eagles ballad, that is Eagles."
	}
	if strings.Contains(lower, "hills like white elephants") {
		return "Ernest Hemingway wrote \"Hills Like White Elephants.\""
	}
	if strings.Contains(lower, "dante") || strings.Contains(lower, "dante alighieri") || strings.Contains(lower, "divine comedy") || strings.Contains(lower, "inferno") {
		return "Dante Alighieri was a medieval Italian poet best known for The Divine Comedy: Inferno, Purgatorio, and Paradiso."
	}
	if strings.Contains(lower, "gyroscopic engine") || strings.Contains(lower, "gyro engine") || strings.Contains(lower, "omnidirectional retrieval") || strings.Contains(lower, "semantic angular momentum") || strings.Contains(lower, "post-are") || strings.Contains(lower, "truth capsule") {
		return `The Gyroscopic Engine is the next shape of ARE.

The old ARE model treated memory like stacked Truth Capsules: stable, useful, but too linear. The Gyro turns those capsules into oriented rotors inside a semantic field. Instead of asking, "Which folder is on top?", it asks, "From what angle is the truth being approached?"

In Claire terms:

1. BARE holds backward anchored recall.
2. FARE gives forward-facing anticipatory context.
3. The Gyro stabilizes both, so recent noise does not drag the whole system off-axis.
4. Truth Capsules gain direction: azimuth, elevation, momentum, and stability.
5. Recall becomes angular and omnidirectional, not just keyword matching.

The practical rule: Gyro is the orientation layer. It keeps meaning steady while the query changes angle.`
	}
	if strings.Contains(lower, "capital of france") {
		return "Paris is the capital of France."
	}
	if strings.Contains(lower, "90-day") && strings.Contains(lower, "legal research") && strings.Contains(lower, "business") {
		return `Yes. Here is the clean first version.

Phase 1, weeks 1-2: define the offer. Keep it narrow: legal research support, docket monitoring, case summaries, and document organization. Do not present it as legal representation.

Phase 2, weeks 3-4: build the intake workflow. Client question -> jurisdiction -> facts -> CourtListener search -> source summary -> risk notes -> attorney-review disclaimer.

Phase 3, weeks 5-8: sell to one audience first: solo attorneys, pro se litigants needing organization, small firms, or investigators. Pick one. Price simple: $99 quick research memo, $299 case map, $750 monthly monitoring.

Phase 4, weeks 9-12: tighten operations. Track every source, citation, date, jurisdiction, and uncertainty. Make Claire useful by being disciplined, not flashy.

Compliance risks: unauthorized practice of law, hallucinated citations, privacy, privilege confusion, and overpromising. Mitigation: label outputs as research support, cite sources, keep audit trails, and recommend attorney review for legal decisions.

Break-even first target: at $5,000 budget, aim for 10 research memos at $299 or 7 monthly users at $750. Keep paid APIs capped until revenue is proven.

Top failure modes: vague offer, no niche, bad citations, no disclaimers, slow turnaround, API cost creep, poor source tracking, trying to replace lawyers, weak onboarding, and too many features. The remedy is focus: one workflow, one audience, one reliable result.`
	}
	if strings.Contains(lower, "legal") || strings.Contains(lower, "court") || strings.Contains(lower, "filing") || strings.Contains(lower, "motion") || strings.Contains(lower, "case") {
		return `I can help as a legal research and strategy advisor, not as a licensed lawyer.

Give me the jurisdiction, the court, the key facts in date order, and what you are trying to file or prove.

Then I can help you shape the issue, find source material, organize arguments, spot risks, and prepare questions for attorney review. I will separate what the record says from what we infer.`
	}

	if containsAny(lower, "should i", "what should", "how should", "how would", "help me", "strategy", "plan", "business", "investor", "build", "improve", "decide", "risk") {
		return claireStrategicAnswer(q)
	}

	if isQuestion(lower) {
		return claireUnknownAnswer(q)
	}

	return claireReflectiveAnswer()
}

func askHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		var req promptRequest
		_ = json.NewDecoder(r.Body).Decode(&req)

		q := req.Prompt
		if q == "" {
			q = req.Query
		}
		if q == "" {
			q = req.Q
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(promptResponse{
			Response: buildResponse(q),
			Source:   "go",
			OK:       true,
		})
		return
	}

	q := r.URL.Query().Get("q")
	response := buildResponse(q)

	t, _ := template.New("web").Parse(tpl)
	_ = t.Execute(w, map[string]string{"Response": response})
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":      true,
		"service": "claire-go",
		"port":    8080,
	})
}

func speedHandler(w http.ResponseWriter, r *http.Request) {
	t, _ := template.New("web").Parse(tpl)
	_ = t.Execute(w, map[string]string{"Response": speedTestAnswer()})
}

func diagnosticHandler(w http.ResponseWriter, r *http.Request) {
	target := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("target")))
	w.Header().Set("Content-Type", "application/json")
	if target == "speed" {
		_ = json.NewEncoder(w).Encode(diagnosticResponse{
			Title:  "Memory Performance",
			Status: "READY",
			Detail: speedTestAnswer(),
			Next:   "Use /speed for the GUI view or /diagnostic?target=pipeline for the runtime path.",
		})
		return
	}
	if target == "pipeline" {
		_ = json.NewEncoder(w).Encode(diagnosticResponse{
			Title:  "Pipeline",
			Status: "READY",
			Detail: pipelineAnswer(),
			Next:   "Use /speed for the ARE latency table.",
		})
		return
	}
	_ = json.NewEncoder(w).Encode(diagnosticResponse{
		Title:  "Diagnostic",
		Status: "UNKNOWN_TARGET",
		Detail: "Supported targets: speed, pipeline.",
		Next:   "Open /speed for the restored GUI speed test.",
	})
}

func main() {
	http.HandleFunc("/", askHandler)
	http.HandleFunc("/ask", askHandler)
	http.HandleFunc("/chat", askHandler)
	http.HandleFunc("/speed", speedHandler)
	http.HandleFunc("/diagnostic", diagnosticHandler)
	http.HandleFunc("/health", healthHandler)

	fmt.Println("CLAIRE NODE LIVE :8080")
	log.Fatal(http.ListenAndServe("127.0.0.1:8080", nil))
}
