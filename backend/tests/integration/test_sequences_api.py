"""api/v1/sequences.py: GET /current auto-seeds the default 7-step sequence,
and POST /steps persists tenant-edited steps - both previously broken
(SequenceStep has no `delay_days` attribute, only `delay_minutes`;
`SequenceStep(..., delay_days=s.delay_days, ...)` raises TypeError on
construction, and `SequenceStepSchema.model_validate(s, from_attributes=True)`
raises for the same reason when reading them back). Fixed by
SequenceStepSchema.from_db()/explicit days<->minutes conversion, matching
the pattern already used for SequenceRule's own interval fields."""
from tests.conftest import bearer_for


async def test_get_current_seeds_and_returns_all_seven_default_steps(client):
    response = await client.get("/api/v1/sequences/current", headers=bearer_for("org_seq_default"))

    assert response.status_code == 200
    data = response.json()
    channels = [s["channel"] for s in data["steps"]]
    assert channels == [
        "LINKEDIN", "LINKEDIN_FOLLOWUP", "EMAIL_1", "EMAIL_2", "CALL", "VOICEMAIL", "BREAKUP_EMAIL",
    ]
    # step_number is 1-indexed and matches array position
    assert [s["step_number"] for s in data["steps"]] == [1, 2, 3, 4, 5, 6, 7]
    # every step has a real integer delay_days field (the bug: this used to
    # not exist on the ORM object at all)
    assert all(isinstance(s["delay_days"], int) for s in data["steps"])


async def test_get_current_is_idempotent_and_does_not_reseed(client):
    first = await client.get("/api/v1/sequences/current", headers=bearer_for("org_seq_idempotent"))
    second = await client.get("/api/v1/sequences/current", headers=bearer_for("org_seq_idempotent"))

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["steps"]) == 7
    assert len(second.json()["steps"]) == 7
    assert [s["id"] for s in first.json()["steps"]] == [s["id"] for s in second.json()["steps"]]


async def test_post_steps_persists_a_custom_reordered_sequence(client):
    # First load /current so a SequenceRule exists to attach steps to.
    await client.get("/api/v1/sequences/current", headers=bearer_for("org_seq_custom"))

    custom_steps = [
        {"channel": "EMAIL_1", "step_number": 1, "title": "Cold Email First", "delay_days": 3},
        {"channel": "LINKEDIN", "step_number": 2, "title": "LinkedIn Second", "delay_days": 2},
    ]
    response = await client.post(
        "/api/v1/sequences/steps", json=custom_steps, headers=bearer_for("org_seq_custom")
    )

    assert response.status_code == 200
    saved = response.json()
    assert len(saved) == 2
    assert saved[0]["channel"] == "EMAIL_1"
    assert saved[0]["delay_days"] == 3
    assert saved[1]["channel"] == "LINKEDIN"
    assert saved[1]["delay_days"] == 2

    # Reading it back must reflect the same custom order - not the default 7.
    current = await client.get("/api/v1/sequences/current", headers=bearer_for("org_seq_custom"))
    assert [s["channel"] for s in current.json()["steps"]] == ["EMAIL_1", "LINKEDIN"]


async def test_post_steps_without_an_existing_rule_returns_404(client):
    response = await client.post(
        "/api/v1/sequences/steps",
        json=[{"channel": "LINKEDIN", "step_number": 1, "title": "x", "delay_days": 1}],
        headers=bearer_for("org_seq_no_rule_yet"),
    )
    assert response.status_code == 404
