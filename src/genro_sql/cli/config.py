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

"""Database configuration management for Genro CLI."""

import json
from pathlib import Path
from typing import Any


class DbConfig:
    """Manages database configuration stored in ~/.genro/db/."""

    def __init__(self):
        """Initialize database configuration manager."""
        self.config_dir = Path.home() / ".genro"
        self.db_dir = self.config_dir / "db"
        self.register_file = self.db_dir / "register.json"

    def ensure_directories(self) -> None:
        """Create configuration directories if they don't exist."""
        self.db_dir.mkdir(parents=True, exist_ok=True)

    def load_register(self) -> dict[str, Any]:
        """Load database register from JSON file.

        Returns:
            Dictionary mapping database names to connection parameters.
        """
        if not self.register_file.exists():
            return {}

        with open(self.register_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_register(self, register: dict[str, Any]) -> None:
        """Save database register to JSON file.

        Args:
            register: Dictionary mapping database names to connection parameters.
        """
        self.ensure_directories()

        with open(self.register_file, "w", encoding="utf-8") as f:
            json.dump(register, f, indent=2, ensure_ascii=False)

    def add(self, name: str, connection_string: str) -> None:
        """Add or update a database connection in the register.

        Args:
            name: Database identifier/name.
            connection_string: Database connection string or path.
        """
        register = self.load_register()
        register[name] = {"connection_string": connection_string}
        self.save_register(register)

    def remove(self, name: str) -> bool:
        """Remove a database from the register.

        Args:
            name: Database identifier/name to remove.

        Returns:
            True if database was removed, False if it didn't exist.
        """
        register = self.load_register()

        if name not in register:
            return False

        del register[name]
        self.save_register(register)
        return True

    def list_all(self) -> dict[str, Any]:
        """List all registered databases.

        Returns:
            Dictionary mapping database names to their configurations.
        """
        return self.load_register()

    def get(self, name: str) -> dict[str, Any] | None:
        """Get configuration for a specific database.

        Args:
            name: Database identifier/name.

        Returns:
            Database configuration dictionary or None if not found.
        """
        register = self.load_register()
        return register.get(name)
