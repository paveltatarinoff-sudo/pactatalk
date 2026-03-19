from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.models.session import SessionState
from bot.services.claude_service import ClaudeService


class InMemoryRepo:
    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, str]]] = {}
        self._events: list[dict[str, Any]] = []

    async def get_history(self, session_id: str) -> list[dict[str, str]]:
        return list(self._history.get(session_id, []))

    async def save_history(self, session_id: str, history: list[dict[str, str]]) -> None:
        self._history[session_id] = list(history)

    async def delete_history(self, session_id: str) -> None:
        self._history.pop(session_id, None)

    async def append_event(self, **kwargs: Any) -> None:
        self._events.append(kwargs)


def _default_scenarios_path() -> Path:
    return Path(__file__).with_name("prompt_scenarios.json")


def _load_scenarios(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_session(raw: dict[str, Any], scenario_id: str) -> SessionState:
    session_data = raw.get("session", {})
    return SessionState(
        session_id=f"prompt-harness-{scenario_id}",
        user_a_id=1,
        user_b_id=2,
        name_a=session_data.get("name_a", "Pasha"),
        name_b=session_data.get("name_b", "Lyuda"),
        waiting_for=session_data.get("waiting_for", "A"),
        dialogue_state=session_data.get("dialogue_state", "SETUP"),
        last_turn_summary=session_data.get("last_turn_summary", ""),
    )


async def _run_scenario(service: ClaudeService, scenario: dict[str, Any]) -> dict[str, Any]:
    repo = InMemoryRepo()
    session = _build_session(scenario, scenario["id"])
    turns = scenario.get("turns", [])
    outputs: list[dict[str, Any]] = []

    for turn in turns:
        message, risk_flag, next_speaker, response_meta = await service.get_facilitator_response(
            session=session,
            user_message=turn["message"],
            sender_label=turn["sender_label"],
            repo=repo,
        )
        outputs.append(
            {
                "input": {
                    "sender_label": turn["sender_label"],
                    "message": turn["message"],
                },
                "response": {
                    "message": message,
                    "risk_flag": risk_flag,
                    "next_speaker": next_speaker,
                    "addressed_to": response_meta.get("addressed_to"),
                    "dialogue_state": session.dialogue_state,
                    "last_turn_summary": session.last_turn_summary,
                },
            }
        )
        session.waiting_for = next_speaker

    history = await repo.get_history(session.session_id)
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "notes": scenario.get("notes", ""),
        "session": {
            "name_a": session.name_a,
            "name_b": session.name_b,
            "waiting_for_start": scenario.get("session", {}).get("waiting_for", "A"),
            "dialogue_state_start": scenario.get("session", {}).get("dialogue_state", "SETUP"),
            "waiting_for_end": session.waiting_for,
            "dialogue_state_end": session.dialogue_state,
        },
        "outputs": outputs,
        "history": history,
    }


def _format_console_result(result: dict[str, Any]) -> str:
    lines = [
        f"=== {result['title']} ({result['id']}) ===",
        f"Notes: {result['notes']}",
        f"Start: waiting_for={result['session']['waiting_for_start']}, state={result['session']['dialogue_state_start']}",
    ]
    for index, item in enumerate(result["outputs"], start=1):
        response = item["response"]
        lines.extend(
            [
                f"Turn {index} input [{item['input']['sender_label']}]: {item['input']['message']}",
                "Model response:",
                response["message"],
                (
                    "Structured: "
                    f"next_speaker={response['next_speaker']}, "
                    f"risk_flag={response['risk_flag']}, "
                    f"dialogue_state={response['dialogue_state']}"
                ),
            ]
        )
    lines.append(
        f"End: waiting_for={result['session']['waiting_for_end']}, state={result['session']['dialogue_state_end']}"
    )
    return "\n".join(lines)


def _format_markdown(results: list[dict[str, Any]]) -> str:
    sections = [f"# Prompt Harness Report\n\nGenerated: {datetime.utcnow().isoformat()}Z"]
    for result in results:
        sections.append(f"## {result['title']} (`{result['id']}`)")
        sections.append(f"- Notes: {result['notes']}")
        sections.append(
            f"- Start: waiting_for=`{result['session']['waiting_for_start']}`, state=`{result['session']['dialogue_state_start']}`"
        )
        for index, item in enumerate(result["outputs"], start=1):
            response = item["response"]
            sections.append(f"### Turn {index}")
            sections.append(f"**Input [{item['input']['sender_label']}]**")
            sections.append(item["input"]["message"])
            sections.append("**Model response**")
            sections.append(response["message"])
            sections.append(
                "- Structured: "
                f"`next_speaker={response['next_speaker']}`, "
                f"`risk_flag={response['risk_flag']}`, "
                f"`dialogue_state={response['dialogue_state']}`"
            )
        sections.append(
            f"- End: waiting_for=`{result['session']['waiting_for_end']}`, state=`{result['session']['dialogue_state_end']}`"
        )
    return "\n\n".join(sections) + "\n"


def _write_output(path: Path, results: list[dict[str, Any]]) -> None:
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    path.write_text(_format_markdown(results), encoding="utf-8")


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight prompt regression scenarios.")
    parser.add_argument("--scenario", help="Run a single scenario by id.")
    parser.add_argument("--list", action="store_true", help="List available scenarios and exit.")
    parser.add_argument(
        "--scenarios-file",
        default=str(_default_scenarios_path()),
        help="Path to JSON file with scenarios.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save results. Use .json for JSON, otherwise markdown is written.",
    )
    args = parser.parse_args()

    scenarios_path = Path(args.scenarios_file)
    scenarios = _load_scenarios(scenarios_path)

    if args.list:
        for scenario in scenarios:
            print(f"{scenario['id']}: {scenario['title']}")
        return 0

    if args.scenario:
        scenarios = [scenario for scenario in scenarios if scenario["id"] == args.scenario]
        if not scenarios:
            raise SystemExit(f"Scenario not found: {args.scenario}")

    service = ClaudeService()
    results = []
    for scenario in scenarios:
        result = await _run_scenario(service, scenario)
        results.append(result)
        print(_format_console_result(result))
        print()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_output(output_path, results)
        print(f"Saved report to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
