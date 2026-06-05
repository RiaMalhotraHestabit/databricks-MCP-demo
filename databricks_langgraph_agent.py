import argparse
import os
import sys
from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from databricks_assistant import (
    extract_text,
    make_mcp_client,
    make_workspace_client,
    looks_like_write_sql,
)


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


def build_tools():
    workspace_client = make_workspace_client()
    sql_client = make_mcp_client(workspace_client, "api/2.0/mcp/sql")
    ai_client = make_mcp_client(workspace_client, "api/2.0/mcp/functions/system/ai")

    @tool
    def execute_databricks_sql(
        query: Annotated[
            str,
            "A read-only Databricks SQL query. Use fully qualified catalog.schema.table names.",
        ],
    ) -> str:
        """Run a read-only SQL query through Databricks SQL MCP."""
        if looks_like_write_sql(query):
            return "Refused: write SQL is not allowed in this agent."

        result = sql_client.call_tool("execute_sql_read_only", {"query": query})
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


def print_agent_answer(result: dict) -> None:
    messages = result.get("messages", [])
    if not messages:
        print("(No response)")
        return

    final_message = messages[-1]
    content = getattr(final_message, "content", final_message)
    print(content)


def ask_agent(agent, question: str) -> None:
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(content=question),
            ]
        },
        config={"recursion_limit": 12},
    )
    print_agent_answer(result)


def interactive_loop(agent) -> None:
    print("Databricks LangGraph agent")
    print("Ask a natural-language question. Type 'quit' to exit.")

    while True:
        try:
            question = input("\nagent> ").strip()
            if not question:
                continue
            if question.lower() in {"quit", "exit"}:
                print("Bye.")
                return
            ask_agent(agent, question)
        except KeyboardInterrupt:
            print("\nBye.")
            return
        except Exception as exc:
            print(f"Error: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Natural-language Databricks assistant using LangGraph and Databricks MCP."
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Natural-language question to ask. Omit for interactive mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        agent = build_agent()
    except Exception as exc:
        print(f"Setup error: {exc}")
        return 2

    question = " ".join(args.question).strip()
    if question:
        ask_agent(agent, question)
    else:
        interactive_loop(agent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
