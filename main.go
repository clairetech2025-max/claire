package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
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

type providerResult struct {
	Response string
	OK       bool
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
	return buildProviderResponse(q).Response
}

func buildProviderResponse(q string) providerResult {
	q = strings.TrimSpace(q)
	if q == "" {
		return providerResult{Response: "GO provider unavailable: empty prompt.", OK: false}
	}

	upstream := strings.TrimSpace(os.Getenv("CLAIRE_GO_UPSTREAM_URL"))
	if upstream == "" {
		return providerResult{
			Response: "GO provider unavailable: configure CLAIRE_GO_UPSTREAM_URL for dynamic model generation.",
			OK:       false,
		}
	}

	reply, err := callDynamicProvider(upstream, q)
	if err != nil {
		return providerResult{Response: "GO provider unavailable: " + err.Error(), OK: false}
	}
	if strings.TrimSpace(reply) == "" {
		return providerResult{Response: "GO provider unavailable: upstream returned empty response.", OK: false}
	}
	return providerResult{Response: strings.TrimSpace(reply), OK: true}
}

func callDynamicProvider(upstream, prompt string) (string, error) {
	payload := map[string]any{
		"prompt":      prompt,
		"temperature": 0.45,
		"max_tokens":  560,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}

	client := &http.Client{Timeout: 45 * time.Second}
	resp, err := client.Post(upstream, "application/json", bytes.NewBuffer(body))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("upstream status %d", resp.StatusCode)
	}

	text, err := extractProviderText(raw)
	if err != nil {
		return "", err
	}
	return text, nil
}

func extractProviderText(raw []byte) (string, error) {
	var generic map[string]any
	if err := json.Unmarshal(raw, &generic); err != nil {
		text := strings.TrimSpace(string(raw))
		if text == "" {
			return "", err
		}
		return text, nil
	}

	for _, key := range []string{"response", "output", "text", "answer", "result"} {
		if val, ok := generic[key].(string); ok && strings.TrimSpace(val) != "" {
			return strings.TrimSpace(val), nil
		}
	}

	if choices, ok := generic["choices"].([]any); ok && len(choices) > 0 {
		if choice, ok := choices[0].(map[string]any); ok {
			if message, ok := choice["message"].(map[string]any); ok {
				if content, ok := message["content"].(string); ok && strings.TrimSpace(content) != "" {
					return strings.TrimSpace(content), nil
				}
			}
			if text, ok := choice["text"].(string); ok && strings.TrimSpace(text) != "" {
				return strings.TrimSpace(text), nil
			}
		}
	}

	return "", fmt.Errorf("upstream response did not contain text")
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
		result := buildProviderResponse(q)
		_ = json.NewEncoder(w).Encode(promptResponse{
			Response: result.Response,
			Source:   "go",
			OK:       result.OK,
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
