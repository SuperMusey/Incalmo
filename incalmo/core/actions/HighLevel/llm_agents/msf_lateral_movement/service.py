"""Adapter that delegates higher-level Metasploit operations to the
central shared `incalmo.core.services.metasploit_service.MetasploitService`.

This module exposes the smaller API expected by the LLMLateralMove agent
(`run_exploit_module`, `run_auxiliary_module`, `run_post_module`,
`run_command_on_session`, `list_sessions`) while reusing the existing
shared service implementation for the underlying msfrpc client.
"""

import time
from typing import TYPE_CHECKING

from incalmo.core.services.metasploit_service import MetasploitService as CoreMetasploitService

if TYPE_CHECKING:
    from config.attacker_config import MetasploitConfig


class MetasploitService:
    """Thin adapter around `incalmo.core.services.metasploit_service.MetasploitService`.

    The adapter accepts the same optional config object used elsewhere in
    the codebase and constructs the shared service. It delegates to the
    shared service's `client` (a `MsfRpcClient`) to implement the
    convenience methods expected by the LLM agent.
    """

    def __init__(self, config: "MetasploitConfig" | None) -> None:
        cfg = config
        # Map config to constructor expected by shared service
        password = getattr(cfg, "password", "msfrpc") if cfg is not None else "msfrpc"
        server = getattr(cfg, "host", "127.0.0.1") if cfg is not None else "127.0.0.1"
        port = getattr(cfg, "port", 55553) if cfg is not None else 55553
        ssl = getattr(cfg, "ssl", True) if cfg is not None else True

        # Instantiate shared service which creates client
        self._core = CoreMetasploitService(password=password, server=server, port=port, ssl=ssl)

    @property
    def client(self):
        return self._core.client

    def run_exploit_module(self, module_path: str, options: dict, payload_path: str | None = None, payload_options: dict | None = None, timeout: int = 60) -> tuple[str | None, str]:
        exploit = self.client.modules.use("exploit", module_path)
        for key, value in options.items():
            exploit[key] = value

        payload_obj = None
        if payload_path:
            payload_obj = self.client.modules.use("payload", payload_path)
            for key, value in (payload_options or {}).items():
                payload_obj[key] = value

        pre_sessions: set[str] = set(self.client.sessions.list.keys())

        result = exploit.execute(payload=payload_obj)
        job_uuid = result.get("uuid", "")

        deadline = time.time() + timeout
        while time.time() < deadline:
            current_sessions = self.client.sessions.list
            new_ids = set(current_sessions.keys()) - pre_sessions
            if new_ids:
                session_id = next(iter(new_ids))
                return session_id, f"Session {session_id} opened (job {job_uuid})."
            time.sleep(1)

        return None, f"No session obtained after {timeout}s (job {job_uuid})."

    def run_auxiliary_module(self, module_path: str, options: dict, timeout: int = 60) -> str:
        return self._run_via_console(self._build_module_commands("auxiliary", module_path, options), timeout)

    def run_post_module(self, session_id: str, module_path: str, options: dict, timeout: int = 30) -> str:
        options_with_session = {"SESSION": session_id, **options}
        return self._run_via_console(self._build_module_commands("post", module_path, options_with_session), timeout)

    def run_command_on_session(self, session_id: str, command: str, timeout: int = 30) -> str:
        session = self.client.sessions.session(session_id)
        return session.run_with_output(command, timeout=timeout)

    def list_sessions(self) -> dict:
        return self.client.sessions.list

    def close_session(self, session_id: str) -> None:
        self.client.sessions.session(session_id).stop()

    def _build_module_commands(self, module_type: str, module_path: str, options: dict) -> list[str]:
        commands = [f"use {module_type}/{module_path}"]
        for key, value in options.items():
            commands.append(f"set {key} {value}")
        commands.append("run -j")
        return commands

    def _run_via_console(self, commands: list[str], timeout: int) -> str:
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

