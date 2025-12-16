# Copyright (c) 2025 Softwell Srl, Milano, Italy
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Database management commands for Genro CLI."""

import sys
from argparse import ArgumentParser, _SubParsersAction

from genro_sql.cli.config import DbConfig


class DbCommands:
    """Database management commands."""

    @staticmethod
    def register_parser(subparsers: _SubParsersAction) -> None:
        """Register the 'db' subcommand and its sub-subcommands.

        Args:
            subparsers: The subparsers action from the main argument parser.
        """
        # Create the 'db' subcommand parser
        db_parser = subparsers.add_parser(
            "db",
            help="Manage database connections",
            description="Register and manage database connections for Genro applications",
        )

        # Create sub-subparsers for db commands
        db_subparsers = db_parser.add_subparsers(
            title="database commands",
            dest="db_command",
            help="Use 'genro db <command> --help' for command-specific help",
        )

        # Add subcommand
        add_parser = db_subparsers.add_parser(
            "add",
            help="Register a new database connection",
        )
        add_parser.add_argument("name", help="Database identifier name")
        add_parser.add_argument("connection_string", help="Database connection string or path")

        # List subcommand
        db_subparsers.add_parser(
            "list",
            help="List all registered databases",
        )

        # Get subcommand
        get_parser = db_subparsers.add_parser(
            "get",
            help="Get information about a specific database",
        )
        get_parser.add_argument("name", help="Database identifier name")

        # Remove subcommand
        remove_parser = db_subparsers.add_parser(
            "remove",
            help="Remove a registered database",
        )
        remove_parser.add_argument("name", help="Database identifier name to remove")

    @staticmethod
    def execute(args) -> None:
        """Execute the database command.

        Args:
            args: Parsed command-line arguments.
        """
        config = DbConfig()

        if not args.db_command:
            print("Error: No database command specified. Use 'genro db --help' for usage.", file=sys.stderr)
            sys.exit(1)

        if args.db_command == "add":
            DbCommands._add(config, args.name, args.connection_string)
        elif args.db_command == "list":
            DbCommands._list(config)
        elif args.db_command == "get":
            DbCommands._get(config, args.name)
        elif args.db_command == "remove":
            DbCommands._remove(config, args.name)
        else:
            print(f"Error: Unknown command '{args.db_command}'", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def _add(config: DbConfig, name: str, connection_string: str) -> None:
        """Add a database to the register.

        Args:
            config: Database configuration manager.
            name: Database identifier name.
            connection_string: Database connection string or path.
        """
        try:
            # Check if database already exists
            existing = config.get(name)
            if existing:
                print(f"Warning: Database '{name}' already exists. Updating...", file=sys.stderr)

            config.add(name, connection_string)
            print(f"Database '{name}' registered successfully.")
            print(f"Configuration saved to: {config.register_file}")
        except Exception as e:
            print(f"Error registering database: {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def _list(config: DbConfig) -> None:
        """List all registered databases.

        Args:
            config: Database configuration manager.
        """
        try:
            databases = config.list_all()

            if not databases:
                print("No databases registered.")
                print(f"Use 'genro db add <name> <connection_string>' to register a database.")
                return

            print(f"Registered databases ({len(databases)}):")
            print()
            for name, info in databases.items():
                print(f"  {name}:")
                print(f"    Connection: {info.get('connection_string', 'N/A')}")
        except Exception as e:
            print(f"Error listing databases: {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def _get(config: DbConfig, name: str) -> None:
        """Get information about a specific database.

        Args:
            config: Database configuration manager.
            name: Database identifier name.
        """
        try:
            db_info = config.get(name)

            if not db_info:
                print(f"Error: Database '{name}' not found.", file=sys.stderr)
                print(f"Use 'genro db list' to see registered databases.", file=sys.stderr)
                sys.exit(1)

            print(f"Database: {name}")
            print(f"Connection: {db_info.get('connection_string', 'N/A')}")
        except Exception as e:
            print(f"Error getting database info: {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def _remove(config: DbConfig, name: str) -> None:
        """Remove a database from the register.

        Args:
            config: Database configuration manager.
            name: Database identifier name to remove.
        """
        try:
            if config.remove(name):
                print(f"Database '{name}' removed successfully.")
            else:
                print(f"Error: Database '{name}' not found.", file=sys.stderr)
                print(f"Use 'genro db list' to see registered databases.", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"Error removing database: {e}", file=sys.stderr)
            sys.exit(1)
