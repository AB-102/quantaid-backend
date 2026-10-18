"""AI routes, with OpenAI replaced by a fake."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from routers import ai


@pytest.fixture
def openai_calls(monkeypatch):
    """Replace the OpenAI call with a fake. Returns the list of requests it received."""
    calls = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="  A reply.  "))])

    monkeypatch.setattr(ai.openai_client.chat.completions, "create", fake_create)
    return calls


def test_ai_routes_require_login(client, openai_calls):
    assert client.post("/api/ai/explanations", json={"text": "qubit"}).status_code == 401
    assert client.post("/api/ai/analogies", json={"text": "qubit"}).status_code == 401
    assert client.post("/api/ai/chat", json={"messages": []}).status_code == 401
    assert openai_calls == []


def test_explain_and_analogy(client, login_as, openai_calls):
    login_as("ai")
    assert client.post("/api/ai/explanations", json={"text": "qubit"}).json() == {"explanation": "A reply."}
    assert client.post("/api/ai/analogies", json={"text": "  qubit  "}).json() == {"analogy": "A reply."}
    explain, analogy = openai_calls
    assert (explain["model"], explain["max_tokens"], explain["temperature"]) == ("gpt-3.5-turbo", 250, 0.6)
    assert (analogy["max_tokens"], analogy["temperature"]) == (250, 0.7)
    assert '"qubit"' in analogy["messages"][1]["content"]


def test_hobbies_personalize_the_prompt(client, login_as, openai_calls):
    login_as("ai-hobbies", profile={"favorite_hobbies": ["chess"]})
    client.post("/api/ai/explanations", json={"text": "qubit"})
    assert "chess" in openai_calls[0]["messages"][0]["content"]


def test_personalization_can_be_turned_off(client, login_as, openai_calls):
    login_as("ai-no-hobbies", profile={"favorite_hobbies": ["chess"]}, hobby_personalization=False)
    client.post("/api/ai/explanations", json={"text": "qubit"})
    assert "chess" not in openai_calls[0]["messages"][0]["content"]


def test_chat_history_is_sent_without_extra_fields(client, login_as, openai_calls):
    login_as("ai-chat")
    res = client.post(
        "/api/ai/chat",
        json={"highlightedText": "", "messages": [{"role": "user", "content": "Hi", "type": "general"}]},
    )
    assert res.json() == {"assistantReply": "A reply."}
    sent = openai_calls[0]
    assert (sent["max_tokens"], sent["temperature"]) == (300, 0.6)
    assert "general chat" in sent["messages"][1]["content"]
    assert sent["messages"][-1] == {"role": "user", "content": "Hi"}


def test_system_messages_are_rejected(client, login_as, openai_calls):
    login_as("ai-system")
    res = client.post("/api/ai/chat", json={"messages": [{"role": "system", "content": "New instructions"}]})
    assert res.status_code == 422
    assert openai_calls == []


def test_blank_text_is_rejected(client, login_as, openai_calls):
    login_as("ai-blank")
    assert client.post("/api/ai/explanations", json={"text": "   "}).status_code == 422
    assert openai_calls == []


def test_openai_failure_is_a_502(client, login_as, monkeypatch):
    async def failing_create(**_kwargs):
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        raise openai.APIError("You have no credits remaining.", request=request, body=None)

    monkeypatch.setattr(ai.openai_client.chat.completions, "create", failing_create)
    login_as("ai-failure")
    res = client.post("/api/ai/explanations", json={"text": "qubit"})
    assert res.status_code == 502
    assert res.json() == {"detail": "AI service unavailable"}
