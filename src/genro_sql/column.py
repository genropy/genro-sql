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

"""Column definition with metadata and lazy type resolution."""

from typing import Any, Optional

from genro_core.lib import get_type_catalog


class Column:
    """
    Column definition with Genropy type system.

    Attributes:
        name: Logical column name
        sql_name: SQL column name in database (defaults to name if not set)
        dtype: Genropy type code ('T', 'L', 'D', 'N', etc.)
        name_long: Long descriptive name
        name_plural: Plural name
        size: Size specification (for CHAR/VARCHAR/NUMERIC)
        not_null: If True, column cannot be NULL
        default: Default value
    """

    def __init__(
        self,
        name: str,
        dtype: str,
        sql_name: Optional[str] = None,
        name_long: Optional[str] = None,
        name_plural: Optional[str] = None,
        size: Any = None,
        not_null: bool = False,
        default: Any = None,
        **metadata
    ):
        self.name = name
        self.sql_name = sql_name or name  # Default to name if not specified
        self.dtype = dtype
        self.name_long = name_long
        self.name_plural = name_plural
        self.size = size
        self.not_null = not_null
        self.default = default
        self.metadata = metadata

        # Cache for lazy properties
        self._python_type = None
        self._sql_type = None

    @property
    def python_type(self) -> type:
        """
        Get Python type for this column (lazy, cached).

        Uses TypeCatalog to convert Genropy dtype to Python type.
        """
        if self._python_type is None:
            catalog = get_type_catalog()
            self._python_type = catalog.get_python_type(self.dtype)
        return self._python_type

    @property
    def sql_type(self) -> str:
        """
        Get SQL type for this column (lazy, cached).

        Uses TypeCatalog to convert Genropy dtype to SQL type,
        applying size if present.
        """
        if self._sql_type is None:
            catalog = get_type_catalog()
            base_type = catalog.get_sql_type(self.dtype)

            # Apply size specification
            if self.size is not None:
                if self.dtype == 'C':
                    # CHAR with fixed size
                    if isinstance(self.size, int):
                        self._sql_type = f'CHAR({self.size})'
                    else:
                        self._sql_type = f'CHAR({self.size})'
                elif self.dtype == 'T':
                    # VARCHAR with range
                    if isinstance(self.size, str) and ':' in self.size:
                        _, max_len = self.size.split(':')
                        self._sql_type = f'VARCHAR({max_len})'
                    elif isinstance(self.size, int):
                        self._sql_type = f'VARCHAR({self.size})'
                    else:
                        self._sql_type = base_type
                elif self.dtype == 'N':
                    # NUMERIC with precision/scale
                    if isinstance(self.size, str) and ',' in self.size:
                        self._sql_type = f'NUMERIC({self.size})'
                    else:
                        self._sql_type = base_type
                else:
                    self._sql_type = base_type
            else:
                self._sql_type = base_type

        return self._sql_type

    def to_dict(self) -> dict:
        """Convert column to dictionary representation."""
        return {
            'name': self.name,
            'sql_name': self.sql_name,
            'dtype': self.dtype,
            'name_long': self.name_long,
            'name_plural': self.name_plural,
            'size': self.size,
            'not_null': self.not_null,
            'default': self.default,
            **self.metadata
        }

    def __repr__(self) -> str:
        return f"Column(name='{self.name}', sql_name='{self.sql_name}', dtype='{self.dtype}')"
