from __future__ import annotations

import os
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from .clients import make_mcp_client, make_workspace_client
from .config import load_settings
from .sql_guardrails import prepare_sql_query


load_dotenv()

SYSTEM_PROMPT = """
You are a Databricks data assistant connected to Databricks MCP tools.

You can:
- run read-only Databricks SQL using execute_databricks_sql
- run self-contained standard-library Python using run_databricks_python

Rules:
- Use Databricks SQL syntax.
- Only run read-only SQL. Use SELECT, SHOW, DESCRIBE, DESC, EXPLAIN, or WITH.
- Do not run INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, MERGE, or TRUNCATE.
- Prefer discovery commands before guessing table names:
  SHOW CATALOGS
  SHOW SCHEMAS IN catalog_name
  SHOW TABLES IN catalog_name.schema_name
  DESCRIBE TABLE catalog_name.schema_name.table_name
- Use fully qualified Unity Catalog names when querying tables:
  catalog.schema.table
- If the user asks a broad data question but you do not know the table,
  first inspect catalogs/schemas/tables, then ask a concise follow-up if needed.
- Summarize query results clearly for the user.
""".strip()


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    last_user_message: str | None


def build_tools():
    settings = load_settings()
    workspace_client = make_workspace_client(settings)
    sql_client = make_mcp_client(workspace_client, "api/2.0/mcp/sql", host=settings.databricks_host)
    ai_client = make_mcp_client(
        workspace_client,
        "api/2.0/mcp/functions/system/ai",
        host=settings.databricks_host,
    )

    @tool
    def execute_databricks_sql(
        query: Annotated[
            str,
            "A read-only Databricks SQL query. Use fully qualified catalog.schema.table names.",
        ],
    ) -> str:
        """Run a read-only SQL query through Databricks SQL MCP."""
        validated = prepare_sql_query(query, settings, allow_write_override=False)
        result = sql_client.call_tool("execute_sql_read_only", {"query": validated})
        return extract_text(result)

    @tool
    def run_databricks_python(
        code: Annotated[
            str,
            "Self-contained Python code using only the standard library. It must print the final answer.",
        ],
    ) -> str:
        """Run Python through Databricks AI Functions MCP."""
        result = ai_client.call_tool("system__ai__python_exec", {"code": code})
        return extract_text(result)

    return [execute_databricks_sql, run_databricks_python]


def extract_text(result) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(item))

    if parts:
        return "\n".join(parts)
    return str(result)


def build_agent():
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add your Claude key to .env before running this agent."
        )

    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise RuntimeError(
            "langchain-anthropic is not installed. Install it with: pip install langchain-anthropic"
        ) from exc

    model_name = os.getenv("ANTHROPIC_MODEL", "").strip()
    if not model_name:
        raise RuntimeError("ANTHROPIC_MODEL is not set. Add a Claude Haiku model name to .env.")
    if "haiku" not in model_name.lower():
        raise RuntimeError(
            f"ANTHROPIC_MODEL must be a Claude Haiku model, got: {model_name}"
        )

    base_llm = ChatAnthropic(model=model_name, temperature=0)
    tools = build_tools()
    llm = base_llm.bind_tools(tools)

    def call_model(state: AgentState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        response = llm.invoke(messages)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


def _last_ai_message(messages: list) -> AIMessage | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message
        if getattr(message, "type", None) == "ai":
            return message
    return None


def print_agent_answer(result: dict) -> None:
    messages = result.get("messages", [])
    if not messages:
        print("(No response)")
        return

    final_message = _last_ai_message(messages) or messages[-1]
    content = getattr(final_message, "content", final_message)
    print(f"\nassistant> {content}")


def run_turn(agent, messages: list, question: str) -> list:
    result = agent.invoke(
        {
            "messages": [*messages, HumanMessage(content=question)],
            "last_user_message": question,
        },
        config={"recursion_limit": 12},
    )
    print_agent_answer(result)
    return result.get("messages", messages)


def ask_agent(agent, question: str) -> None:
    run_turn(agent, [], question)


def print_chat_banner() -> None:
    print("Databricks MCP chat")
    print("Ask natural-language questions and the agent will route to SQL or Python tools.")
    print("Type /help for commands, /tools to inspect the available tools, and /quit to exit.")


def print_chat_help() -> None:
    print(
        """
Commands:
  /help    Show this message
  /tools   Show the tools this agent can use
  /clear   Reset the conversation context
  /quit    Exit the chat

You can ask normal questions like:
  show me the available catalogs
  what schemas are in main
  summarize this query result
""".strip()
    )


def interactive_loop(agent, tools: list | None = None) -> None:
    print_chat_banner()

    if tools:
        tool_names = ", ".join(getattr(tool, "name", str(tool)) for tool in tools)
        print(f"Tools: {tool_names}")

    messages: list = []

    while True:
        try:
            question = input("\nuser> ").strip()
            if not question:
                continue

            lowered = question.lower()
            if lowered in {"/quit", "quit", "exit"}:
                print("Bye.")
                return
            if lowered == "/help":
                print_chat_help()
                continue
            if lowered == "/clear":
                messages = []
                print("Conversation cleared.")
                continue
            if lowered == "/tools":
                if tools:
                    print("Available tools:")
                    for tool in tools:
                        print(f"- {getattr(tool, 'name', str(tool))}")
                else:
                    print("No tool metadata available.")
                continue

            messages = run_turn(agent, messages, question)
        except KeyboardInterrupt:
            print("\nBye.")
            return
        except Exception as exc:
            print(f"Error: {exc}")
