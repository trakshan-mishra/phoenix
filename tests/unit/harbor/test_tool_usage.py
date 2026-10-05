from typing import Any

from harbor_verifiers import tool_usage


def _call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_call_id": name, "function_name": name, "arguments": arguments}


def _trajectory(*calls: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": "ATIF-v1.7",
        "steps": [
            {"source": "user", "message": "question", "timestamp": "2026-10-02T10:00:00Z"},
            {"source": "agent", "tool_calls": list(calls), "timestamp": "2026-10-02T10:00:05Z"},
            {
                "source": "agent",
                "is_copied_context": True,
                "tool_calls": [_call("executeSql", sql="select 1")],
                "timestamp": "2026-10-01T00:00:00Z",
            },
            {"source": "agent", "message": "done", "timestamp": "2026-10-02T10:01:35Z"},
        ],
        **extra,
    }


def test_direct_sql_tools_count_as_sql_whatever_the_client_prefix() -> None:
    assert tool_usage.categories(_call("executeSql", sql="select 1")) == {"sql"}
    assert tool_usage.categories(_call("mcp__phoenix__describeSqlSchema")) == {"sql"}
    assert tool_usage.categories(_call("mcp__phoenix-dev__executeSql", sql="select 1")) == {"sql"}


def test_code_mode_execute_is_classified_by_the_tools_it_calls() -> None:
    sql = _call("mcp__phoenix__execute", code='s = await call_tool("executeSql", {"sql": "x"})')
    rest = _call("mcp__phoenix__execute", code="ds = await call_tool('listDatasets', {})")
    both = _call(
        "execute",
        code='a = await call_tool("describeSqlSchema", {})\nb = await call_tool("getDataset", {})',
    )
    meta = _call("mcp__phoenix__execute", code='await call_tool("list_tools", {})')
    assert tool_usage.categories(sql) == {"sql"}
    assert tool_usage.categories(rest) == {"rest"}
    assert tool_usage.categories(both) == {"sql", "rest"}
    assert tool_usage.categories(meta) == set()


def test_discovery_tools_reach_no_surface() -> None:
    for name in ("mcp__phoenix__list_tools", "mcp__phoenix__search", "ToolSearch", "Read"):
        assert tool_usage.categories(_call(name)) == set()


def test_shell_commands_are_classified_by_what_they_run() -> None:
    assert tool_usage.categories(
        _call("Bash", command="px api graphql '{ projects { edges { node { name } } } }'")
    ) == {"graphql"}
    assert tool_usage.categories(_call("bash", command="phoenix-gql schema --search cost")) == {
        "graphql"
    }
    assert tool_usage.categories(
        _call("Bash", command="curl -s http://localhost:6006/graphql -d '{}'")
    ) == {"graphql"}
    assert tool_usage.categories(_call("Bash", command="px projects list --format json")) == {
        "rest"
    }
    assert tool_usage.categories(
        _call("Bash", command="curl $PHOENIX/v1/projects/p/spans?limit=5")
    ) == {"rest"}
    assert (
        tool_usage.categories(_call("Bash", command="ls -la /app && grep -n phoenix setup.py"))
        == set()
    )
    assert (
        tool_usage.categories(_call("Bash", command="pip install px-tool && npx something"))
        == set()
    )


def test_rest_tools_are_camel_case_operation_ids_and_graphql_tools_say_so() -> None:
    assert tool_usage.categories(_call("listProjects")) == {"rest"}
    assert tool_usage.categories(_call("mcp__phoenix__getDatasetExamples", id="x")) == {"rest"}
    assert tool_usage.categories(_call("phoenix_gql", query="{ projectCount }")) == {"graphql"}
    assert tool_usage.categories(_call("call_subagent", prompt="x")) == set()
    assert tool_usage.categories(_call("ask_user", question="x")) == set()


def test_surface_usage_counts_calls_and_skips_copied_context() -> None:
    trajectory = _trajectory(
        _call("mcp__phoenix__execute", code='await call_tool("executeSql", {"sql": "select 1"})'),
        _call("executeSql", sql="select 2"),
        _call("Bash", command="px api graphql '{ projectCount }'"),
        _call("Read", file_path="/app/x"),
    )
    assert tool_usage.surface_usage(trajectory) == {
        "used_sql": 1.0,
        "sql_call_count": 2.0,
        "used_graphql": 1.0,
        "graphql_call_count": 1.0,
        "used_rest": 0.0,
        "rest_call_count": 0.0,
    }


def test_run_metrics_prefer_final_metrics_and_measure_wall_clock() -> None:
    trajectory = _trajectory(
        final_metrics={
            "total_prompt_tokens": 1000,
            "total_completion_tokens": 50,
            "total_cached_tokens": 900,
            "total_cost_usd": 0.25,
            "total_steps": 3,
        }
    )
    assert tool_usage.run_metrics(trajectory) == {
        "prompt_tokens": 1000.0,
        "completion_tokens": 50.0,
        "cached_tokens": 900.0,
        "cost_usd": 0.25,
        "latency_s": 95.0,
    }


def test_run_metrics_sum_step_metrics_when_there_are_no_totals() -> None:
    trajectory = _trajectory()
    trajectory["steps"][1]["metrics"] = {"prompt_tokens": 10, "completion_tokens": 2}
    trajectory["steps"][3]["metrics"] = {"prompt_tokens": 20, "completion_tokens": 3}
    assert tool_usage.run_metrics(trajectory) == {
        "prompt_tokens": 30.0,
        "completion_tokens": 5.0,
        "latency_s": 95.0,
    }
    assert tool_usage.run_metrics(None) == {}


def test_diagnostics_are_all_numeric() -> None:
    values = tool_usage.diagnostics(_trajectory(_call("executeSql", sql="select 1")))
    assert values and all(isinstance(value, float) for value in values.values())


def test_shell_heuristics_ignore_lookalikes() -> None:
    for command in (
        "which phoenix px python3; grep -n px SKILL.md",
        "curl https://api.openai.com/v1/models",
        "grep -rn x $PKG/server/api/routers/v1/spans.py",
    ):
        assert tool_usage.categories(_call("Bash", command=command)) == set(), command
    assert tool_usage.categories(_call("Bash", command="cd /app\npx datasets list")) == {"rest"}
    assert tool_usage.categories(
        _call("Bash", command="curl -s http://127.0.0.1:6006/v1/datasets")
    ) == {"rest"}
