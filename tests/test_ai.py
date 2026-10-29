"""AI routes and the daily limit, with OpenAI replaced by a fake."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import openai
import pytest

from routers import ai
from schemas.ai import MAX_TEXT_LENGTH
from services import llm_service


@pytest.fixture
def openai_calls(monkeypatch):
    """Replace the OpenAI call with a fake. Returns the list of requests it received."""
    calls = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="  A reply.  "))])

    monkeypatch.setattr(llm_service._quantaid_client.chat.completions, "create", fake_create)
    return calls


@pytest.fixture
def failing_openai(monkeypatch):
    """Make every OpenAI call fail, as it does when the account has run out of credits."""

    async def failing_create(**_kwargs):
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        raise openai.APIError("You have no credits remaining.", request=request, body=None)

    monkeypatch.setattr(llm_service._quantaid_client.chat.completions, "create", failing_create)


@pytest.fixture
def daily_limit(monkeypatch):
    """Lower the daily limit to 2 requests."""
    monkeypatch.setattr("services.ai_usage_service.AI_DAILY_LIMIT", 2)
    return 2


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
    assert (explain["model"], explain["max_tokens"], explain["temperature"]) == (llm_service.DEFAULT_MODEL, 250, 0.6)
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


def test_text_over_the_limit_is_rejected(client, login_as, openai_calls):
    login_as("ai-too-long")
    too_long = "q" * (MAX_TEXT_LENGTH + 1)
    assert client.post("/api/ai/explanations", json={"text": too_long}).status_code == 422
    assert client.post("/api/ai/chat", json={"highlightedText": too_long}).status_code == 422
    assert client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": too_long}]}).status_code == 422
    assert openai_calls == []


def test_chat_sends_only_the_latest_messages(client, login_as, openai_calls):
    login_as("ai-long-chat")
    messages = [{"role": "user", "content": f"Message {n}"} for n in range(15)]
    assert client.post("/api/ai/chat", json={"messages": messages}).status_code == 200
    history = openai_calls[0]["messages"][2:]  # after the system prompt and the highlighted-text message
    assert history == messages[-ai.MAX_CHAT_HISTORY :]


def test_openai_failure_is_a_502(client, login_as, failing_openai):
    login_as("ai-failure")
    res = client.post("/api/ai/explanations", json={"text": "qubit"})
    assert res.status_code == 502
    assert res.json() == {"detail": "AI service unavailable"}


def test_requests_stop_at_the_daily_limit(client, login_as, openai_calls, daily_limit):
    login_as("ai-limit")
    assert client.post("/api/ai/explanations", json={"text": "qubit"}).status_code == 200
    assert client.post("/api/ai/chat", json={"messages": []}).status_code == 200
    res = client.post("/api/ai/analogies", json={"text": "qubit"})
    assert res.status_code == 429
    assert res.json() == {"detail": "Daily AI limit reached"}
    assert len(openai_calls) == daily_limit


def test_a_failed_request_does_not_use_up_the_limit(client, login_as, failing_openai, daily_limit):
    login_as("ai-limit-failure")
    for _ in range(daily_limit + 1):
        assert client.post("/api/ai/explanations", json={"text": "qubit"}).status_code == 502
    assert client.get("/api/me/ai-usage").json()["used"] == 0


def test_admins_have_no_daily_limit(client, login_as, openai_calls, daily_limit):
    login_as("ai-limit-admin", is_admin=True)
    for _ in range(daily_limit + 1):
        assert client.post("/api/ai/explanations", json={"text": "qubit"}).status_code == 200
    assert client.get("/api/me/ai-usage").json() == {"used": 0, "limit": None, "resetsAt": None}


def test_the_limit_resets_each_day(client, login_as, test_db, openai_calls, daily_limit):
    email = login_as("ai-limit-yesterday")
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    test_db.ai_usage.insert_one({"user_id": email, "day": today - timedelta(days=1), "count": daily_limit})
    assert client.post("/api/ai/explanations", json={"text": "qubit"}).status_code == 200


def test_ai_usage_reports_todays_count(client, login_as, openai_calls, daily_limit):
    login_as("ai-usage")
    client.post("/api/ai/explanations", json={"text": "qubit"})
    for _ in range(daily_limit):
        client.post("/api/ai/analogies", json={"text": "qubit"})
    usage = client.get("/api/me/ai-usage").json()
    # Refused requests aren't reported as used beyond the limit
    assert (usage["used"], usage["limit"]) == (daily_limit, daily_limit)
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    assert datetime.fromisoformat(usage["resetsAt"]) == datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=UTC
    )


def test_ai_usage_requires_login(client):
    assert client.get("/api/me/ai-usage").status_code == 401
