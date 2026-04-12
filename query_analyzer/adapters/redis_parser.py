"""Redis SLOWLOG parser and command analyzer."""

from typing import Any


class RedisParser:
    """Parser for Redis SLOWLOG entries and command analysis.

    Analyzes Redis commands from SLOWLOG to identify dangerous O(N) operations
    that may impact performance: KEYS, SMEMBERS, HGETALL, LRANGE without limit,
    SORT, and set operations (SINTER, SUNION). Normalizes commands to a
    standardized format compatible with AntiPatternDetector.

    Attributes:
        dangerous_commands: Mapping of dangerous commands to severity penalties
    """

    # Dangerous commands with penalty and reason
    DANGEROUS_PATTERNS = {
        "KEYS": ("O(N) bloqueante, escanea todo el keyspace", -25),
        "SMEMBERS": ("O(N) sin paginación", -25),
        "HGETALL": ("O(N) sin paginación", -20),
        "LRANGE": ("O(N) potencial si rango es 0 -1", -20),
        "SORT": ("O(N + M log M) costoso", -25),
        "SINTER": ("O(N+M) para múltiples sets", -15),
        "SUNION": ("O(N+M) para múltiples sets", -15),
        "FLUSHDB": ("Operación destructiva O(N)", -30),
        "FLUSHALL": ("Operación destructiva O(N)", -30),
    }

    @staticmethod
    def parse_slowlog_entry(entry: list) -> dict[str, Any]:
        """Parse raw SLOWLOG entry into structured dict.

        With decode_responses=True, entry items are already strings.
        Format: [id, timestamp, duration_us, command_array, client, client_addr]

        Args:
            entry: Raw SLOWLOG entry from SLOWLOG GET command

        Returns:
            Dictionary with parsed entry:
                - id: Entry ID
                - timestamp: Unix timestamp
                - duration_ms: Duration in milliseconds (converted from microseconds)
                - command: Full command string (space-joined)
                - client: Client address
                - client_addr: Client IP and port
        """
        entry_id, timestamp, duration_us, command_array, client, client_addr = entry

        # command_array is already list of strings (decode_responses=True)
        command_str = " ".join(command_array)

        return {
            "id": entry_id,
            "timestamp": timestamp,
            "duration_ms": duration_us / 1000.0,  # Convert microseconds to ms
            "command": command_str,
            "client": client,
            "client_addr": client_addr,
        }

    @staticmethod
    def parse_command(command_str: str) -> dict[str, Any]:
        """Parse command string into components.

        Extracts command name, arguments, and raw string for analysis.

        Args:
            command_str: Full command string (e.g., "SET mykey myvalue")

        Returns:
            Dictionary with:
                - command: Uppercase command name (e.g., "SET")
                - args: List of arguments
                - raw: Original command string
        """
        parts = command_str.split()
        if not parts:
            return {"command": "", "args": [], "raw": command_str}

        return {
            "command": parts[0].upper(),
            "args": parts[1:],
            "raw": command_str,
        }

    @staticmethod
    def detect_dangerous_command(command: str) -> tuple[bool, str, float]:
        """Detect dangerous command pattern.

        Command is already a string (no bytes handling needed due to
        decode_responses=True). Checks for O(N) operations and destructive
        commands that may impact Redis performance.

        Args:
            command: Full command string

        Returns:
            Tuple of (is_dangerous, reason, penalty):
                - is_dangerous: True if command matches dangerous pattern
                - reason: Human-readable explanation
                - penalty: Score penalty (-25 to -30)
        """
        command_upper = command.split()[0].upper()

        if command_upper in RedisParser.DANGEROUS_PATTERNS:
            reason, penalty = RedisParser.DANGEROUS_PATTERNS[command_upper]
            return (True, reason, penalty)

        # Check for LRANGE with full range (0 -1)
        if command_upper == "LRANGE" and "0" in command and "-1" in command:
            return (True, "LRANGE 0 -1 fetches entire list (O(N))", -20)

        return (False, "", 0)

    @staticmethod
    def normalize_plan(command: str) -> dict[str, Any]:
        """Normalize Redis command to standardized format.

        Converts Redis command into AntiPatternDetector-compatible structure
        for unified anti-pattern analysis across database engines.

        Args:
            command: Full Redis command string

        Returns:
            Normalized plan dictionary with:
                - node_type: Redis operation type (e.g., "KEYS_SCAN", "SET_ITERATION")
                - command: Original command name
                - complexity: Time complexity (e.g., "O(N)")
                - is_blocking: True if operation blocks Redis thread
                - data_structure: Redis data structure involved
                - estimated_rows: Always None (unknown without MEMORY USAGE)
                - filter_condition: Query filter if any
                - extra_info: List of optimization notes
                - children: Empty list (Redis doesn't have nested operations like SQL)
        """
        parsed = RedisParser.parse_command(command)
        command_upper = parsed["command"]
        is_dangerous, danger_reason, _ = RedisParser.detect_dangerous_command(command)

        # Map commands to node types and structures
        node_type_map = {
            "KEYS": "KEYS_SCAN",
            "SMEMBERS": "SET_ITERATION",
            "HGETALL": "HASH_ITERATION",
            "LRANGE": "LIST_RANGE",
            "SORT": "SORT_OPERATION",
            "SINTER": "SET_INTERSECTION",
            "SUNION": "SET_UNION",
            "FLUSHDB": "FLUSH_OPERATION",
            "FLUSHALL": "FLUSH_OPERATION",
        }

        node_type = node_type_map.get(command_upper, "UNKNOWN")

        # Complexity mapping
        complexity_map = {
            "KEYS": "O(N)",
            "SMEMBERS": "O(N)",
            "HGETALL": "O(N)",
            "LRANGE": "O(N)",
            "SORT": "O(N + M log M)",
            "SINTER": "O(N+M)",
            "SUNION": "O(N+M)",
            "FLUSHDB": "O(N)",
            "FLUSHALL": "O(N)",
        }

        complexity = complexity_map.get(command_upper, "O(1)")

        # Data structure type
        structure_map = {
            "KEYS": "KEYS",
            "SMEMBERS": "SET",
            "SINTER": "SET",
            "SUNION": "SET",
            "HGETALL": "HASH",
            "LRANGE": "LIST",
            "SORT": "GENERIC",
            "FLUSHDB": "ALL",
            "FLUSHALL": "ALL",
        }

        data_structure = structure_map.get(command_upper, "UNKNOWN")

        # Blocking operations
        blocking_commands = {"KEYS", "SORT", "FLUSHDB", "FLUSHALL"}
        is_blocking = command_upper in blocking_commands

        # Extra info
        extra_info = []
        if is_dangerous:
            extra_info.append(danger_reason)

        if is_blocking:
            extra_info.append("Blocks Redis thread during execution")

        # Recommendations based on command
        if command_upper == "KEYS":
            extra_info.append("Use SCAN cursor for pagination instead")
        elif command_upper == "SMEMBERS":
            extra_info.append("Use SSCAN for large sets")
        elif command_upper == "HGETALL":
            extra_info.append("Use HSCAN for large hashes or get specific fields")
        elif command_upper in ["LRANGE", "SORT"]:
            extra_info.append("Add LIMIT or pagination to reduce rows")
        elif command_upper in ["SINTER", "SUNION"]:
            extra_info.append("Consider pre-computing intersections if frequently used")

        return {
            "node_type": node_type,
            "command": command_upper,
            "complexity": complexity,
            "is_blocking": is_blocking,
            "data_structure": data_structure,
            "estimated_rows": None,  # Unknown without MEMORY USAGE
            "filter_condition": None,
            "extra_info": extra_info,
            "children": [],
        }
