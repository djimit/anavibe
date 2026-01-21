"""Command-line interface for Anavibe MCP A2A.

Provides commands for:
- Starting the server
- Managing agents
- Generating keys and tokens
- Health checks
"""

import argparse
import sys
from typing import NoReturn

from anavibe import __version__


def main() -> NoReturn:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="anavibe",
        description="Anavibe MCP A2A - Agent-to-Agent Communication Framework",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("serve", help="Start the API server")
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    server_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    server_parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker processes (default: 4)",
    )

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate keys and tokens")
    gen_subparsers = gen_parser.add_subparsers(dest="gen_type", help="What to generate")

    gen_subparsers.add_parser("secret-key", help="Generate a secret key")
    gen_subparsers.add_parser("api-key", help="Generate an API key")
    gen_subparsers.add_parser("encryption-key", help="Generate a Fernet encryption key")

    # Health check command
    health_parser = subparsers.add_parser("health", help="Check server health")
    health_parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Server URL (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    if args.command == "serve":
        run_server(args)
    elif args.command == "generate":
        run_generate(args)
    elif args.command == "health":
        run_health_check(args)
    else:
        parser.print_help()
        sys.exit(0)

    sys.exit(0)


def run_server(args: argparse.Namespace) -> None:
    """Run the API server."""
    import os

    import uvicorn

    # Set environment variables from args if not already set
    if args.host:
        os.environ.setdefault("HOST", args.host)
    if args.port:
        os.environ.setdefault("PORT", str(args.port))
    if args.reload:
        os.environ.setdefault("RELOAD", "true")
    if args.workers:
        os.environ.setdefault("WORKERS", str(args.workers))

    print(f"Starting Anavibe MCP A2A server v{__version__}")
    print(f"Listening on {args.host}:{args.port}")

    uvicorn.run(
        "anavibe.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=1 if args.reload else args.workers,
    )


def run_generate(args: argparse.Namespace) -> None:
    """Generate keys and tokens."""
    import secrets

    if args.gen_type == "secret-key":
        key = secrets.token_urlsafe(32)
        print("Generated Secret Key:")
        print(f"  {key}")
        print("\nAdd to your .env file:")
        print(f"  SECRET_KEY={key}")

    elif args.gen_type == "api-key":
        key = f"av_{secrets.token_hex(32)}"
        print("Generated API Key:")
        print(f"  {key}")
        print("\nStore this securely - it cannot be retrieved later!")

    elif args.gen_type == "encryption-key":
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        print("Generated Fernet Encryption Key:")
        print(f"  {key}")
        print("\nAdd to your .env file:")
        print(f"  A2A_ENCRYPTION_KEY={key}")

    else:
        print("Usage: anavibe generate [secret-key|api-key|encryption-key]")
        sys.exit(1)


def run_health_check(args: argparse.Namespace) -> None:
    """Check server health."""
    import json

    import httpx

    url = f"{args.url.rstrip('/')}/api/v1/health"

    try:
        response = httpx.get(url, timeout=10.0)
        data = response.json()

        if response.status_code == 200:
            print(f"Server Status: {data.get('status', 'unknown')}")
            print(f"Version: {data.get('version', 'unknown')}")
            print(f"Timestamp: {data.get('timestamp', 'unknown')}")

            checks = data.get("checks", {})
            if checks:
                print("\nHealth Checks:")
                for check, status in checks.items():
                    print(f"  - {check}: {status}")
        else:
            print(f"Health check failed with status {response.status_code}")
            print(json.dumps(data, indent=2))
            sys.exit(1)

    except httpx.ConnectError:
        print(f"Failed to connect to {url}")
        print("Is the server running?")
        sys.exit(1)
    except Exception as e:
        print(f"Health check failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
