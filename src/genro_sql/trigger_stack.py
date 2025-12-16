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

"""Trigger stack system for preventing infinite recursion in triggers."""

import functools
from typing import Any, Callable


def in_triggerstack(method: Callable) -> Callable:
    """
    Decorator to prevent infinite recursion in trigger chains.

    When a method decorated with @in_triggerstack is called, it checks
    if the same method (identified by name and table instance) is already
    executing in the current call stack. If it is, the method returns
    immediately without executing again.

    This prevents infinite loops when triggers call methods that trigger
    other triggers that eventually call back to the original trigger.

    Usage:
        class MyTable(Table):
            @in_triggerstack
            def trigger_onInserting(self, record):
                # This won't cause infinite recursion
                self.db.tables.other_table.insert(record={'related': 'data'})

    Args:
        method: Method to wrap with trigger stack protection

    Returns:
        Wrapped method with recursion protection
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs) -> Any:
        # Get the trigger stack from currentEnv
        trigger_stack = self.db.currentEnv.setdefault('_trigger_stack', [])

        # Create unique identifier for this method call
        # Format: "table_name.method_name"
        trigger_id = f"{self.name}.{method.__name__}"

        # Check if already in stack
        if trigger_id in trigger_stack:
            # Already executing - prevent recursion
            return None

        # Add to stack
        trigger_stack.append(trigger_id)

        try:
            # Execute method
            result = method(self, *args, **kwargs)
            return result
        finally:
            # Remove from stack
            if trigger_id in trigger_stack:
                trigger_stack.remove(trigger_id)

    return wrapper
