import argparse
import sys
from mhc.method_history_collector import *

_DASH_VALUE_OPTIONS = {"--java-options", "--command-options"}
_KNOWN_OPTION_FLAGS = {
    "--cache-directory",
    "--repository-directory",
    "--data-directory",
    "--jar-directory",
    "--tool-name",
    "--command-options",
    "--java-options",
    "--timeout-seconds",
    "--project",
}


def _normalize_dash_prefixed_option_values(argv: list[str]) -> list[str]:
    normalized_argv = []
    index = 0

    while index < len(argv):
        token = argv[index]
        if (
            token in _DASH_VALUE_OPTIONS
            and index + 1 < len(argv)
            and argv[index + 1].startswith("-")
            and argv[index + 1] != "--"
            and argv[index + 1] not in _KNOWN_OPTION_FLAGS
        ):
            normalized_argv.append(f"{token}={argv[index + 1]}")
            index += 2
            continue

        normalized_argv.append(token)
        index += 1

    return normalized_argv


def _build_method_history_collector(
    cache_directory: str,
    repository_directory: str,
    data_directory: str,
    jar_directory: str,
) -> MethodHistoryCollector:
    return MethodHistoryCollector(
        cache_directory,
        repository_directory,
        data_directory,
        jar_directory,
    )


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Method History Collector (MHC)")

    parser.add_argument(
        "command", type=str, help="Command to execute (e.g., history, call-graph)"
    )
    parser.add_argument(
        "--cache-directory",
        type=str,
        required=True,
        help="Cache directory path"
    )
    parser.add_argument(
        "--repository-directory",
        type=str,
        required=True,
        help="Repository directory path",
    )
    parser.add_argument(
        "--data-directory",
        type=str,
        required=True,
        help="Data directory path"
    )
    parser.add_argument(
        "--jar-directory",
        type=str,
        required=True,
        help="Jar directory path"
    )

    # Conditional args for history command
    parser.add_argument(
        "--tool-name", dest="tool_name", type=str, help="Tool name (required for history command)"
    )
    parser.add_argument(
        "--command-options",
        dest="command_options",
        type=str,
        help="Optional extra arguments forwarded to the underlying command or jar.",
    )
    parser.add_argument(
        "--java-options",
        dest="java_options",
        type=str,
        help="Optional JVM arguments passed before -jar, for example '-Xmx4g'.",
    )
    parser.add_argument(
        "--timeout-seconds",
        dest="timeout_seconds",
        type=int,
        default=30 * 60,
        help="Subprocess timeout in seconds for history jar execution (default: 1800).",
    )
    parser.add_argument(
        "--project",
        dest="project",
        type=str,
        help="Project name (required for project-scoped commands)",
    )

    normalized_argv = _normalize_dash_prefixed_option_values(
        list(sys.argv[1:] if argv is None else argv)
    )
    args = parser.parse_args(normalized_argv)

    mhc = _build_method_history_collector(
        args.cache_directory,
        args.repository_directory,
        args.data_directory,
        args.jar_directory,
    )

    if args.command.lower() == "history":
        if not args.tool_name or not args.project:
            print(
                "Error: tool_name and project are required for history command."
            )
            sys.exit(1)
        mhc.collect_method_history(
            [args.project],
            [args.tool_name],
            args.command_options,
            args.java_options,
            args.timeout_seconds,
        )
    elif args.command.lower() == "call-graph":
        if not args.tool_name or not args.project:
            print(
                "Error: tool_name and project are required for call graph command."
            )
            sys.exit(1)
        mhc.generate_call_graph([args.project], [args.tool_name])
    elif args.command.lower() == "scan-method":
        if not args.project:
            print("Error: project are required to scan methods.")
            sys.exit(1)
        mhc.scan_method([args.project], args.java_options)
    elif args.command.lower() == "method-code":
        if not args.project:
            print("Error: project is required to generate method code.")
            sys.exit(1)
        mhc.generate_method_code([args.project])
    elif args.command.lower() == "index":
        mhc.update_repository_index()
    elif args.command.lower() == "complexity-analyzer":
        if not args.tool_name or not args.project:
            print(
                "Error: tool_name and project are required for complexity analyzer command."
            )
            sys.exit(1)
        mhc.run_complexity_analyzer([args.project], args.tool_name)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
