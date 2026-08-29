# Akasha Upstream Research for Momo

Reviewed: 2026-08-28  
Local dependency: `akasha-terminal[light]>=1.7.3`  
Upstream evidence: [`v1.7.3` / commit `764b8b413155e1b5b26d66b255aec69fa86ca464`](https://github.com/iii-org/akasha/tree/764b8b413155e1b5b26d66b255aec69fa86ca464)

## Confirmed upstream contract

Akasha keeps its main capabilities separate:

| Capability | Upstream API | Meaning for Momo |
| --- | --- | --- |
| Agent | `akasha.agents(...)` | A LangChain-native, tool-calling conversational agent. It may call only explicitly supplied Tools. |
| Streaming | `stream=True` | The synchronous iterator yields dictionaries with `type` `answer`, optional `thinking`, and `tool`; answer and thinking values are token-level chunks. |
| Tool | `akasha.create_tool(...)` | Typed application callable exposed to the model. The application, not the model, owns validation, authorization, persistence, and side effects. |
| Skill | `skills=[directory]` | A `SKILL.md` directory that provides instructions, resources, and controlled tool capability; it does not replace a typed Tool. |
| RAG | `akasha.RAG(...)` | A separate document ingestion, embedding, retrieval, and answer-generation pipeline. It is not automatically part of an Agent conversation. |
| MCP | `MultiServerMCPClient.get_tools()` -> `akasha.normalize_mcp_tools()` -> `agents(tools=...)` | External tools adapted into the Agent Tool list. Supports local `stdio` and remote Streamable HTTP `/mcp`. |

Sources: [README capability overview](https://github.com/iii-org/akasha/blob/764b8b413155e1b5b26d66b255aec69fa86ca464/README.md#L7-L23), [Agent constructor and LangChain build](https://github.com/iii-org/akasha/blob/764b8b413155e1b5b26d66b255aec69fa86ca464/akasha/agent/agents.py#L179-L283), [stream implementation](https://github.com/iii-org/akasha/blob/764b8b413155e1b5b26d66b255aec69fa86ca464/akasha/agent/agents.py#L485-L568), and [RAG tutorial](https://github.com/iii-org/akasha/blob/764b8b413155e1b5b26d66b255aec69fa86ca464/user-guide/en/tutorials/rag.md#L1-L34).

## Current Momo mapping

[`src/p2026_little_avator/api.py`](../src/p2026_little_avator/api.py) already uses the intended model-only Agent shape:

- Each in-process `Conversation` owns one `akasha.agents(...)` instance.
- It explicitly passes `tools=[]`, no `skills`, `stream=True`, and `thinking=True`.
- `run_agent_message()` runs the synchronous iterator off the FastAPI event loop and relays **only** upstream `answer` events to the conversation SSE endpoint. `thinking`, `tool`, verbose console output, and saved diagnostic logs stay server-side.
- The public SSE contract adds application-owned terminal events (`completed` and sanitized `error`); those are Momo events, not Akasha stream events.

This matches the upstream stream contract and preserves the MVP privacy boundary. The supporting product decision is recorded in [AKASHA_AGENT_CHAT_TASK.md](AKASHA_AGENT_CHAT_TASK.md).

## Implications for the next feature

1. Start with an application-owned, typed Tool for a narrow Momo capability such as reminders or todos. Keep storage, validation, identifiers, and permission checks outside Akasha; pass only the allowed callable into `tools=[...]`. Upstream explicitly warns against unrestricted shell, filesystem, database, or network Tools. [Tool tutorial](https://github.com/iii-org/akasha/blob/764b8b413155e1b5b26d66b255aec69fa86ca464/user-guide/en/tutorials/agents.md#L54-L95)
2. Keep the existing answer-only chat SSE contract. If a Tool runs, surface a deliberately designed Momo status event only when the product needs it; do not forward raw Tool arguments/results or thinking text.
3. Do not add a Skill merely to implement CRUD. Use one only when the feature needs an auditable instruction-and-resource workflow. Skill directories can include executable scripts, so they need the same review and allowlisting discipline. [Skill tutorial](https://github.com/iii-org/akasha/blob/764b8b413155e1b5b26d66b255aec69fa86ca464/user-guide/en/tutorials/skill.md#L1-L102)
4. Treat RAG as a later, separately scoped feature: choose document roots explicitly, present retrieval/source behavior in the UX, and define index deletion/retention. It requires a separately configured embedding model in addition to the chat model.
5. Defer MCP until an external service is specifically required. Inspect the discovered Tool list and trust boundary first. Crucially, normalized MCP Tools are async-only: upstream rejects synchronous `stream=True` Agent execution with them and directs callers to `stream=False`. Momo would need an adapter/design change before combining token-level answer SSE with MCP. [MCP tutorial](https://github.com/iii-org/akasha/blob/764b8b413155e1b5b26d66b255aec69fa86ca464/user-guide/en/tutorials/mcp.md#L69-L140) and [async-only guard](https://github.com/iii-org/akasha/blob/764b8b413155e1b5b26d66b255aec69fa86ca464/akasha/agent/agents.py#L573-L592).

## Recommended MVP boundary

Use ordinary Akasha Tools, not an Akasha-core change, for the first capability. A reminder/todo service should own durable records and schedule delivery through Momo's existing global event broker; the Agent only proposes calls through tightly typed Tool inputs. This uses Akasha for model-directed tool selection while retaining application control over real-world effects.
