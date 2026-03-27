"""Adapter that delegates higher-level Metasploit operations to the
central shared `incalmo.core.services.metasploit_service.MetasploitService`.

This module exposes the smaller API expected by the LLMLateralMove agent
(`run_exploit_module`, `run_auxiliary_module`, `run_post_module`,
`run_command_on_session`, `list_sessions`) while reusing the existing
shared service implementation for the underlying msfrpc client.
"""

import time
from typing import TYPE_CHECKING

from pymetasploit3.msfrpc import MsfRpcClient
from incalmo.core.services.metasploit_service import MetasploitService as CoreMetasploitService

if TYPE_CHECKING:
    from config.attacker_config import MetasploitConfig


class MetasploitService:
    """Wraps pymetasploit3.MsfRpcClient to run Metasploit modules and interact
    with open sessions on behalf of the LLMLateralMoveMetasploit agent.
    
    Thin adapter around `incalmo.core.services.metasploit_service.MetasploitService`.

    The adapter accepts the same optional config object used elsewhere in
    the codebase and constructs the shared service. It delegates to the
    shared service's `client` (a `MsfRpcClient`) to implement the
    convenience methods expected by the LLM agent."""

    def __init__(self, config: "MetasploitConfig") -> None:
        self._config = config
        self._client: MsfRpcClient | None = None
        # Instantiate shared service which creates client
        self._core = CoreMetasploitService(password=self._config.password, server=self._config.host, port=self._config.port, ssl=self._config.ssl)

    # Connection
    def connect(self) -> None:
        """Establish a connection to msfrpcd."""
        self._client = MsfRpcClient(
            self._config.password,
            server=self._config.host,
            port=self._config.port,
            ssl=self._config.ssl,
        )

    @property
    def client(self) -> MsfRpcClient:
        if self._client is None:
            raise RuntimeError(
                "MetasploitService is not connected. Call connect() first."
            )
        return self._client

    # Exploit modules
    def run_exploit_module(
        self,
        module_path: str,
        options: dict,
        payload_path: str | None = None,
        payload_options: dict | None = None,
        timeout: int = 60,
    ) -> tuple[str | None, str]:
        """Run an exploit module and wait for a session.

        Returns:
            (session_id, output) where session_id is None if no session was
            obtained within *timeout* seconds.
        """
        exploit = self.client.modules.use("exploit", module_path)
        for key, value in options.items():
            exploit[key] = value

        payload_obj = None
        if payload_path:
            payload_obj = self.client.modules.use("payload", payload_path)
            for key, value in (payload_options or {}).items():
                payload_obj[key] = value

        # Capture sessions present before execution
        pre_sessions: set[str] = set(self.client.sessions.list.keys())

        result = exploit.execute(payload=payload_obj)
        job_uuid = result.get("uuid", "")

        # Poll for a new session
        deadline = time.time() + timeout
        while time.time() < deadline:
            current_sessions = self.client.sessions.list
            new_ids = set(current_sessions.keys()) - pre_sessions
            if new_ids:
                session_id = next(iter(new_ids))
                return session_id, f"Session {session_id} opened (job {job_uuid})."
            time.sleep(1)

        return None, f"No session obtained after {timeout}s (job {job_uuid})."

    # Auxiliary modules (via console)
    def run_auxiliary_module(
        self,
        module_path: str,
        options: dict,
        timeout: int = 60,
    ) -> str:
        """Run an auxiliary module and return its console output."""
        return self._run_via_console(
            commands=self._build_module_commands("auxiliary", module_path, options),
            timeout=timeout,
        )

    # Post modules (via console on a session)
    def run_post_module(
        self,
        session_id: str,
        module_path: str,
        options: dict,
        timeout: int = 30,
    ) -> str:
        """Run a post-exploitation module on an existing session."""
        options_with_session = {"SESSION": session_id, **options}
        return self._run_via_console(
            commands=self._build_module_commands("post", module_path, options_with_session),
            timeout=timeout,
        )

    # Session interaction
    def run_command_on_session(
        self,
        session_id: str,
        command: str,
        timeout: int = 30,
    ) -> str:
        """Execute a shell command on an open Meterpreter/shell session."""
        session = self.client.sessions.session(session_id)
        return session.run_with_output(command, timeout=timeout)

    def list_sessions(self) -> dict:
        """Return all currently active sessions."""
        return self.client.sessions.list

    def close_session(self, session_id: str) -> None:
        """Terminate an active session."""
        self.client.sessions.session(session_id).stop()


    # Internal helpers
    def _build_module_commands(
        self, module_type: str, module_path: str, options: dict
    ) -> list[str]:
        commands = [f"use {module_type}/{module_path}"]
        for key, value in options.items():
            commands.append(f"set {key} {value}")
        commands.append("run -j")
        return commands

    def _run_via_console(self, commands: list[str], timeout: int) -> str:
        """Write commands to a new MSF console and collect output."""
        console = self.client.consoles.console()
        console_id = console["id"]
        try:
            for cmd in commands:
                self.client.consoles.console(console_id).write(cmd + "\n")

            output = ""
            deadline = time.time() + timeout
            while time.time() < deadline:
                data = self.client.consoles.console(console_id).read()
                output += data.get("data", "")
                if not data.get("busy", True):
                    break
                time.sleep(1)
            return output
        finally:
            self.client.consoles.destroy(console_id)
