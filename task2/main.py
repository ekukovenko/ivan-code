# main.py
"""
Coding Agent CLI

Usage:
    python main.py                     # Interactive mode
    python main.py -c "your command"   # Run with initial command
    python main.py --help              # Show help
"""

import argparse
from ui import CodingAgentApp


def main():
    parser = argparse.ArgumentParser(
        description="Coding Agent - AI помощник программиста",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py
    python main.py -c "list files in current directory"
    python main.py -c "fix bug in @test_project/todo_cli.py"
    python main.py -c "run python test_project/todo_cli.py list and fix any errors"
        """
    )
    parser.add_argument(
        "-c", "--command",
        type=str,
        help="Initial command to run"
    )

    args = parser.parse_args()

    app = CodingAgentApp(initial_command=args.command)
    app.run()


if __name__ == "__main__":
    main()
