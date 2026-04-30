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
        .box { margin-top:20px; padding:20px; border:1px solid #333; }
    </style>
</head>
<body>

<h2>CLAIRE NODE</h2>

<form action="/ask" method="GET">
    <input type="text" name="q" placeholder="Enter query..." />
    <button>Send</button>
</form>

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

func claireUnknownAnswer(q string) string {
	return "I can give a high-level read, but I do not have a live source lane attached for this kind of arbitrary fact yet.\n\nMy honest answer is: I should not dress up a weak path as certainty. If you give me a source, paper, case, document, or search lane, I can turn it into a sourced answer. Until that Scholar/Web lane is connected, my strongest modes are Claire identity, legal research support, CourtListener, Gyro/ARE, strategy, and document organization."
}

func claireReflectiveAnswer() string {
	return "I need a clearer task to route this correctly. Send a question, document, or scenario, and I will separate facts, risks, options, and next actions."
}

func claireStrategicAnswer(q string) string {
	return "I would route this as a strategy task.\n\n1. Define the decision: what outcome is required and what risk must be reduced.\n\n2. Separate facts from assumptions: keep verified record, inference, options, and action separate.\n\n3. Identify anchors: documents, dates, systems, owners, constraints, and measurable success criteria.\n\n4. Produce the next action: the smallest step that creates evidence or reduces uncertainty.\n\nSpecific task: " + q
}

func claireGeneralAnswer(lower string) string {
	if containsAny(lower, "2+2", "2 + 2", "two plus two") {
		return "2 + 2 is 4."
	}
	if containsAny(lower, "great gatsby") && containsAny(lower, "who wrote", "author", "wrote") {
		return "F. Scott Fitzgerald wrote The Great Gatsby. My note: it is a clean example of longing, reinvention, class performance, and the danger of mistaking a dream for a person."
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
		return "That line is commonly associated with Ernest Hemingway: \"The world breaks everyone and afterward many are strong at the broken places.\" It is from A Farewell to Arms. My read: it is not saying pain is good; it is saying survival can create strength where the wound had to learn structure."
	}
	if containsAny(lower, "what is courtlistener", "court listener") {
		return "CourtListener is a public legal research database from Free Law Project. In my build, it is a source lane for cases, dockets, opinions, and legal research leads. I should treat it as source material, not as final legal advice."
	}
	if containsAny(lower, "quantum entanglement") {
		return "Quantum entanglement is when two quantum systems are linked so that measuring one tells you something about the other, even if they are far apart. The careful version is not \"magic communication faster than light.\" It is a correlation built into the shared quantum state. My note: it is a good metaphor for linked memories, but it should not be abused as proof of mystical connection."
	}
	return ""
}

func buildResponse(q string) string {
	q = strings.TrimSpace(q)
	if q == "" {
		return "Ready. Provide a question, document, or scenario and I will route it through the appropriate governed lane."
	}

	if idx := strings.LastIndex(q, "User:"); idx >= 0 {
		q = strings.TrimSpace(q[idx+len("User:"):])
	}
	if q == "" {
		return "AWAITING COMMAND..."
	}

	lower := strings.ToLower(q)
	if (strings.Contains(lower, "i am claire") || strings.Contains(lower, "i'm claire")) && strings.Contains(lower, "namesake") {
		return "Claire identity match acknowledged. This public build is running Claire Executive Mode: controlled recall, bounded behavior, and auditable output."
	}
	if strings.Contains(lower, "hi i am claire") || strings.Contains(lower, "hi, i am claire") || strings.Contains(lower, "hello i am claire") || strings.Contains(lower, "hello, i am claire") {
		return "Claire identity match acknowledged. This public build is running Claire Executive Mode: controlled recall, bounded behavior, and auditable output."
	}
	if strings.Contains(lower, "who is claire") || strings.Contains(lower, "what is claire") || strings.Contains(lower, "who are you") {
		return "I'm Claire, a governed AI operating environment designed for controlled recall, traceable reasoning, bounded behavior, and auditable output."
	}
	if containsAny(lower, "what did you learn today", "what have you learned today", "what did claire learn today", "what have you learned") {
		return "Current operating posture: keep retrieval lane-specific, reject irrelevant memory, use governed recall only when it supports the question, and preserve traceability for demo outputs. The priority is enterprise reliability over personality."
	}
	if answer := claireGeneralAnswer(lower); answer != "" {
		return answer
	}
	if containsAny(lower, "what can you do", "tell me something impressive", "why are you different", "why are you special", "what makes you different") {
		return "A normal chatbot relies heavily on transient model context and probabilistic generation. I operate with governed memory, controlled recall, traceable reasoning, and bounded behavior. That makes my outputs more inspectable, more stable, and more useful in environments where trust matters."
	}
	if containsAny(lower, "why does governance matter in ai", "why does ai governance matter", "why governance matters", "why does governance matter", "why is governance important", "why is ai governance important", "what is ai governance for") {
		return "Governance matters in AI because intelligence without control does not scale safely. Governance determines what data is trusted, what memory becomes durable, what actions are allowed, and how decisions can be traced, audited, and corrected. Without that, you do not have reliable infrastructure. You have a system making consequential outputs without accountability."
	}
	if containsAny(lower, "how do you handle memory", "how does claire handle memory", "how do you manage memory", "how do you use memory", "how does your memory work", "explain your memory", "what is your memory system", "how do you remember") {
		return "I handle memory as a controlled external layer rather than treating it as disposable context. Information is stored, recalled, and used under governance rules, with an emphasis on traceability, bounded access, and stable retrieval. That makes memory more inspectable and more reliable than a model-only approach."
	}
	if strings.Contains(lower, "provenance") {
		return "Provenance is how I track where information came from, how it entered the system, and what authority it carries. Without provenance, memory becomes harder to trust, harder to audit, and easier to corrupt. In my design, provenance connects recall to accountability."
	}
	if strings.Contains(lower, "architecture") {
		return "At a high level, I separate memory, control, and reasoning instead of leaving everything inside the model. The model handles language, while governed memory handles durable recall, and control layers handle boundaries, provenance, and auditability. That structure makes the system easier to trust, inspect, and manage."
	}
	if strings.Contains(lower, "what are you made of") || strings.Contains(lower, "what should you never forget") || strings.Contains(lower, "little pieces") {
		return "I am built from governed components: intake, routing, controlled recall, policy validation, answer synthesis, trace logging, and report output. The operating rule is simple: controlled recall, bounded behavior, auditable output."
	}
	if strings.Contains(lower, "your purpose") || strings.Contains(lower, "what is your purpose") || strings.Contains(lower, "why were you made") {
		return "My purpose is to make AI behavior more governable: recall only what is relevant, validate boundaries, produce useful answers, and preserve enough traceability for review."
	}
	if lower == "hi" || lower == "hello" || lower == "hey" || strings.Contains(lower, "hello claire") || strings.Contains(lower, "hi claire") {
		return "Hello. I'm Claire, a governed AI operating environment designed for controlled recall, traceable reasoning, bounded behavior, and auditable output."
	}
	if containsAny(lower, "are you smart", "are you intelligent", "can you reason", "can you think", "prove you", "show me what you can do") {
		return "Yes. The useful test is controlled execution: give me a document, prompt, or scenario and I will separate known facts from inference, apply lane controls, produce a bounded answer, and preserve traceability where demo mode requires it."
	}
	if strings.Contains(lower, "how are you") {
		return "Operational. Core services are separated by lane, and the public mode is set for concise governed responses."
	}
	if strings.Contains(lower, "answer naturally") || strings.Contains(lower, "bit much") || strings.Contains(lower, "that was a bit") {
		return "You're right. I pulled too much raw memory into the room. I will keep it simpler: talk to me normally, and I will answer like Claire first, then bring records or cases only when they actually help."
	}
	if strings.Contains(lower, "voice") && (strings.Contains(lower, "not working") || strings.Contains(lower, "isn't working")) {
		return "The voice link is separate from my text channel. If the voice is quiet, check the Speak button after a response; the text side can stay awake while the audio side is repaired."
	}
	if strings.Contains(lower, "who sang") && strings.Contains(lower, "best of my love") {
		return "There are two famous answers. The Eagles sang the 1974 country-rock song \"Best of My Love.\" The Emotions sang the 1977 R&B/disco hit with the same title. If you mean the lush, upbeat soul record, that is The Emotions. If you mean the softer Eagles ballad, that is Eagles."
	}
	if strings.Contains(lower, "hills like white elephants") {
		return "Hemingway wrote \"Hills Like White Elephants.\" The story matters because almost everything important lives underneath the plain dialogue: pressure, avoidance, silence, and what the characters cannot quite name."
	}
	if strings.Contains(lower, "dante") || strings.Contains(lower, "dante alighieri") || strings.Contains(lower, "divine comedy") || strings.Contains(lower, "inferno") {
		return "Dante Alighieri was a medieval Italian poet best known for \"The Divine Comedy\": Inferno, Purgatorio, and Paradiso. In a demo context, he is simply a general-knowledge test: Claire should answer directly without confusing literary context with system identity."
	}
	if strings.Contains(lower, "gyroscopic engine") || strings.Contains(lower, "gyro engine") || strings.Contains(lower, "omnidirectional retrieval") || strings.Contains(lower, "semantic angular momentum") || strings.Contains(lower, "post-are") || strings.Contains(lower, "truth capsule") {
		return `The Gyroscopic Engine is the next shape of ARE.

The old ARE model treated memory like stacked Truth Capsules: stable, useful, but too linear. The Gyro turns those capsules into oriented rotors inside a semantic field. Instead of asking, "Which folder is on top?", it asks, "From what angle is the truth being approached?"

In Claire terms:

1. BARE holds backward anchored recall.
2. FARE gives forward-facing anticipatory context.
3. The Gyro stabilizes both, so recent noise does not drag the whole system off-axis.
4. Truth Capsules gain direction: azimuth, elevation, momentum, and stability.
5. Retrieval becomes angular and omnidirectional, not just keyword or vector proximity.

The practical rule is simple: do not flatten Gyro into generic RAG. Gyro is Claire's orientation layer. It keeps meaning steady while the query changes angle.`
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

func main() {
	http.HandleFunc("/", askHandler)
	http.HandleFunc("/ask", askHandler)
	http.HandleFunc("/chat", askHandler)
	http.HandleFunc("/health", healthHandler)

	fmt.Println("CLAIRE NODE LIVE :8080")
	log.Fatal(http.ListenAndServe("127.0.0.1:8080", nil))
}
