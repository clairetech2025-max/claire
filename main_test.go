package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestBuildProviderResponseRequiresDynamicProviderWithoutCannedFallback(t *testing.T) {
	t.Setenv("NVIDIA_API_KEY", "")
	t.Setenv("CLAIRE_GO_UPSTREAM_URL", "")

	prompts := []string{
		"Hello",
		"How would you benchmark ARE against FAISS or Pinecone fairly?",
		"Show me your pipeline from input to output.",
		"What is the Ship of Theseus?",
		"Explain ARE without using prior legal or personal memory.",
		"Answer a document question when no document is selected.",
	}
	banned := []string{
		"Hello. I'm Claire",
		"I would route this as a strategy task.",
		"I can give a high-level read",
		"I need a clearer task",
		"At a high level, I separate memory",
		"I can help as a legal research and strategy advisor",
		"The Gyroscopic Engine is the next shape of ARE.",
	}

	for _, prompt := range prompts {
		result := buildProviderResponse(prompt)
		if result.OK {
			t.Fatalf("expected no-upstream prompt %q to return ok=false", prompt)
		}
		if !strings.Contains(result.Response, "GO provider unavailable") {
			t.Fatalf("expected provider-state response for %q, got %q", prompt, result.Response)
		}
		for _, phrase := range banned {
			if strings.Contains(result.Response, phrase) {
				t.Fatalf("prompt %q returned banned canned phrase %q in %q", prompt, phrase, result.Response)
			}
		}
	}
}

func TestBuildProviderResponseProxiesDynamicProvider(t *testing.T) {
	t.Setenv("NVIDIA_API_KEY", "")
	seenPrompt := ""
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected POST, got %s", r.Method)
		}
		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode upstream payload: %v", err)
		}
		seenPrompt, _ = payload["prompt"].(string)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"response": "dynamic upstream answer"})
	}))
	defer server.Close()
	t.Setenv("CLAIRE_GO_UPSTREAM_URL", server.URL)

	result := buildProviderResponse("Hello")
	if !result.OK {
		t.Fatalf("expected ok=true, got %#v", result)
	}
	if result.Response != "dynamic upstream answer" {
		t.Fatalf("unexpected response: %q", result.Response)
	}
	if seenPrompt != "Hello" {
		t.Fatalf("upstream did not receive original prompt, got %q", seenPrompt)
	}
}

func TestAskHandlerPreservesJSONSchema(t *testing.T) {
	t.Setenv("NVIDIA_API_KEY", "")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []map[string]any{{
				"message": map[string]string{"content": "dynamic schema answer"},
			}},
		})
	}))
	defer server.Close()
	t.Setenv("CLAIRE_GO_UPSTREAM_URL", server.URL)

	body := bytes.NewBufferString(`{"prompt":"Show me your pipeline from input to output."}`)
	req := httptest.NewRequest(http.MethodPost, "/", body)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	askHandler(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("unexpected status: %d", w.Code)
	}

	var parsed promptResponse
	if err := json.NewDecoder(w.Body).Decode(&parsed); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !parsed.OK || parsed.Source != "go" || parsed.Response != "dynamic schema answer" {
		t.Fatalf("unexpected provider response: %#v", parsed)
	}
}

func TestBuildProviderResponseUsesNVIDIAChatMessages(t *testing.T) {
	seenAuth := ""
	seenModel := ""
	seenUser := ""
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seenAuth = r.Header.Get("Authorization")
		if got := r.Header.Get("Content-Type"); !strings.Contains(got, "application/json") {
			t.Fatalf("expected JSON content type, got %q", got)
		}
		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode NIM payload: %v", err)
		}
		seenModel, _ = payload["model"].(string)
		messages, ok := payload["messages"].([]any)
		if !ok || len(messages) != 2 {
			t.Fatalf("expected two chat messages, got %#v", payload["messages"])
		}
		if msg, ok := messages[1].(map[string]any); ok {
			seenUser, _ = msg["content"].(string)
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []map[string]any{{
				"message": map[string]string{
					"content":           "visible NIM answer",
					"reasoning_content": "private reasoning field",
				},
			}},
		})
	}))
	defer server.Close()

	t.Setenv("NVIDIA_API_KEY", "test-key-not-real")
	t.Setenv("NVIDIA_NIM_BASE_URL", server.URL)
	t.Setenv("NVIDIA_NIM_MODEL", "test/nemotron")

	result := buildProviderResponse("technical prompt package")
	if !result.OK {
		t.Fatalf("expected NIM ok result, got %#v", result)
	}
	if result.Response != "visible NIM answer" || result.ReasoningContent != "private reasoning field" {
		t.Fatalf("unexpected NIM result: %#v", result)
	}
	if seenAuth != "Bearer test-key-not-real" {
		t.Fatalf("authorization header not set correctly: %q", seenAuth)
	}
	if seenModel != "test/nemotron" {
		t.Fatalf("model not propagated: %q", seenModel)
	}
	if seenUser != "technical prompt package" {
		t.Fatalf("prompt not sent as user message: %q", seenUser)
	}
}

func TestBuildProviderResponseUsesLlamaProfile(t *testing.T) {
	seenModel := ""
	seenUser := ""
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatalf("decode llama payload: %v", err)
		}
		seenModel, _ = payload["model"].(string)
		messages, ok := payload["messages"].([]any)
		if !ok || len(messages) != 2 {
			t.Fatalf("expected two chat messages, got %#v", payload["messages"])
		}
		if msg, ok := messages[1].(map[string]any); ok {
			seenUser, _ = msg["content"].(string)
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []map[string]any{{
				"message": map[string]string{"content": "local llama answer"},
			}},
		})
	}))
	defer server.Close()

	t.Setenv("CLAIRE_PROVIDER", "llama")
	t.Setenv("CLAIRE_LLAMA_URL", server.URL)
	t.Setenv("CLAIRE_LOCAL_MODEL_FILE", "Phi-3-mini-4k-instruct-q4.gguf")
	t.Setenv("NVIDIA_API_KEY", "")

	result := buildProviderResponse("chronology prompt")
	if !result.OK || result.Response != "local llama answer" {
		t.Fatalf("unexpected llama result: %#v", result)
	}
	if seenModel != "Phi-3-mini-4k-instruct-q4.gguf" {
		t.Fatalf("model was not sent from CLAIRE_LOCAL_MODEL_FILE: %q", seenModel)
	}
	if seenUser != "chronology prompt" {
		t.Fatalf("prompt not sent as user chat message: %q", seenUser)
	}
}
