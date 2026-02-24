"""CLI entry point for the remote debug agent.

Usage on the remote machine:
    ducky-remote                      # GUI mode (default)
    ducky-remote --headless script.py  # Headless / CLI mode
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import sys


BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
RESET = "\033[0m"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ducky-remote",
        description="Remote debug agent — run on the machine you want to debug",
    )
    parser.add_argument(
        "program",
        nargs="?",
        default=None,
        help="Program to debug in headless mode (e.g., script.py)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless (CLI) mode instead of launching the GUI",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Interface to listen on (default: 0.0.0.0 = all)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5678,
        help="DAP port for debugger connection (default: 5678)",
    )
    parser.add_argument(
        "--file-port",
        type=int,
        default=0,
        help="File server port (default: auto-assign)",
    )
    args = parser.parse_args()

    if args.headless:
        if not args.program:
            parser.error("--headless requires a program argument")
        _run_headless(args)
    else:
        _run_gui()


def _run_gui() -> None:
    """Launch the PySide6 GUI."""
    try:
        from heyducky.remote.gui.app import run_gui
    except ImportError as e:
        print(f"{RED}error:{RESET} GUI dependencies not installed: {e}")
        print(f"  Install with: {BOLD}pip install ducky[remote]{RESET}")
        print(f"  Or run in headless mode: {BOLD}ducky-remote --headless script.py{RESET}")
        sys.exit(1)
    run_gui()


def _run_headless(args: argparse.Namespace) -> None:
    """Run in headless CLI mode (original behavior)."""
    try:
        asyncio.run(_headless_main(args))
    except KeyboardInterrupt:
        print(f"\n{DIM}Shutting down...{RESET}")


async def _headless_main(args: argparse.Namespace) -> None:
    from heyducky.remote.agent import RemoteAgent, detect_language

    language = detect_language(args.program)
    if not language:
        print(f"{RED}error:{RESET} Could not detect language for {args.program}")
        sys.exit(1)

    agent = RemoteAgent(
        program=args.program,
        language=language,
        host=args.host,
        dap_port=args.port,
        file_port=args.file_port,
    )

    try:
        dap_port, file_port = await agent.start()
    except Exception as e:
        print(f"{RED}error:{RESET} Failed to start: {e}")
        sys.exit(1)

    local_ip = _get_local_ip()

    print()
    print(f"{BOLD}HeyDucky Remote Agent (headless){RESET}")
    print(f"{DIM}{'─' * 40}{RESET}")
    print(f"  Program:     {args.program}")
    print(f"  Language:    {language}")
    print(f"  DAP port:    {dap_port}")
    print(f"  File port:   {file_port}")
    print(f"  Listening:   {args.host}")
    print()
    print(f"  {GREEN}Waiting for HeyDucky to connect...{RESET}")
    print()
    print(f"  {BOLD}On your local machine, press 'r' in HeyDucky and enter:{RESET}")
    print(f"    Host: {BOLD}{local_ip}{RESET}")
    print(f"    Port: {BOLD}{dap_port}{RESET}")
    print()
    print(f"  {DIM}Or from the command line:{RESET}")
    print(f"    ducky --attach {local_ip}:{dap_port} --language {language}")
    print()
    print(f"  {DIM}Ctrl+C to stop{RESET}")
    print()

    try:
        exit_code = await agent.wait()
        if exit_code == 0:
            print(f"{GREEN}Program exited normally.{RESET}")
        else:
            print(f"{YELLOW}Program exited with code {exit_code}.{RESET}")
    finally:
        await agent.stop()


def _get_local_ip() -> str:
    """Best-effort detection of this machine's LAN IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "YOUR_IP"


if __name__ == "__main__":
    main()
