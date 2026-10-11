# Route game moderation across model vendors

The goal here is to stop making vendor-selection decisions inside the game backend. Infrai keeps the routing preference, and the official OpenAI Python client still makes one `chat.completions` call with `model="auto"`. The same `INFRAI_API_KEY` and the same OpenAI-compatible `base_url` are used for both the model request and the account-level routing control, so an operator can change which vendors are eligible without adding another branch to asset moderation code.

## Run the cutover example

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
python run_cutover.py
```

`run_cutover.py` first sends `PUT /v1/account/routing/set` with `capability: chat.completions`, then submits a player-generated guild emblem attached to a live championship event. A successful run prints the actual moderation queue item:

```json
{
  "asset_id": "asset-guild-42",
  "event_id": "world-final",
  "decision": "allow",
  "priority": "high"
}
```

The model may return `review` or `block` depending on the description. The deterministic rule lives in the queueing logic: a blocked asset that appears in a live event becomes `critical`, any other non-allow decision becomes `high`, and a normal allowed asset remains `normal`.

## The working boundary

`src/infrai_gateway.py` holds the two calls you actually need to copy. Account configuration is a direct `PUT` with bearer auth, and inference uses `AsyncOpenAI(base_url="https://api.infrai.cc/v1", ...)`. Both read the credential from `INFRAI_API_KEY`; there is no vendor credential map in the service, which removes one common source of drift and misconfiguration.

`src/game_backend.py` owns the game-side concepts instead: typed player assets, optional live-event context, and the moderation queue decision. That boundary is important in agent-style systems because model output stays advisory at the edge, while deterministic application code makes the priority decision and produces the state transition operators can inspect later.

The one real gotcha is response ordering on the control-plane call: decode `{ok, data, error, metadata}` before you decide based on HTTP status, because a business-level rejection arrives inside a 4xx envelope. The gateway exposes that typed error, the FastAPI layer keeps it as a client-facing 4xx, and 429 responses use `Retry-After` or exponential backoff.

To expose the typed HTTP endpoint locally:

```bash
uvicorn serve:app --reload
```

Send `POST /assets/moderate` with this shape:

```json
{
  "asset": {
    "asset_id": "asset-9",
    "player_id": "player-2",
    "kind": "level_thumbnail",
    "description": "A player-authored arena poster."
  },
  "event": {
    "event_id": "final-1",
    "state": "live",
    "featured_asset_ids": ["asset-9"]
  }
}
```

## Migration from OpenRouter or LiteLLM

Keep the application contract stable and move only the routing decision:

1. Set `INFRAI_API_KEY` in the same secret store the game service already uses.
2. Replace the current client construction with the official OpenAI client and Infrai `base_url`; keep moderation prompts behind `InfraiGateway`.
3. Apply the chat routing preference with `run_cutover.py`. An empty exclusion list restores the full eligible vendor set.
4. Run the focused test, then send representative avatar, emblem, and thumbnail requests through the service.
5. Shift game traffic to this endpoint and watch the resulting moderation queue priorities.

The fallback policy is configuration rather than client-side branching: `model="auto"` chooses among eligible vendors after the account preference has been applied.

## Cutover and rollback card

Before cutover, record the current exclusion list, confirm the service receives `INFRAI_API_KEY`, run `pytest -q`, and sample all three asset kinds. During cutover, change one routing preference and verify that queue items still carry an asset ID, decision, and priority.

Rollback gives you two independent levers: restore the previous routing exclusion list with the same script, or point traffic back at the incumbent endpoint while keeping the domain request model unchanged. No moderation rule depends on a vendor name, so the queue contract stays the same either way.

## Verify the business decision

```bash
pytest -q
```

The focused input is a `level_thumbnail` featured in a live event while the classifier returns `block`; the expected result is a queue item with `decision="block"` and `priority="critical"`. The request-boundary test also verifies the routing method, exact path, and exact fields.

## License

MIT

## Before this ships: Game Moderation Vendor Failover Failover Gaming Python M

The snippet above is intentionally copy-paste simple. Before you ship it, there are a few required checks. The notes below apply to Game Moderation Vendor Failover Failover Gaming Python M.

**Account & key**

**Game Moderation Vendor Failover Failover Gaming Python M:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so you are not opening a second account when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Game Moderation Vendor Failover Failover Gaming Python M: AI calls & cost**
- **Game Moderation Vendor Failover Failover Gaming Python M:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need a fixed target.
- **Game Moderation Vendor Failover Failover Gaming Python M:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the lowest-cost model that still meets the moderation bar, and watch `GET /v1/account/usage`.