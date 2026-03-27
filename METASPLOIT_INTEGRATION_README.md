# Metasploit Integration Changes (Incalmo_R3-25)

Summary
- This directory contains additions that build the Metasploit integration with Incalmo. The changes add an LLM-driven lateral-movement agent and a thin adapter so the agent delegates actual Metasploit work to the shared core service.

What I added
- `incalmo/core/actions/HighLevel/llm_agents/msf_lateral_movement/agent.py` — LLM lateral-movement agent adapted to R3-25.
- `incalmo/core/actions/HighLevel/llm_agents/msf_lateral_movement/service.py` — thin adapter that delegates to the shared core Metasploit service.
- `incalmo/core/actions/HighLevel/llm_agents/msf_lateral_movement/preprompt.txt` — preprompt used by the LLM agent.
- `incalmo/core/actions/HighLevel/llm_agents/msf_lateral_movement/__init__.py` — package export for the agent.
- `METASPLOIT_INTEGRATION_STEPS.txt` — (this file's companion) detailed step-by-step explanation of the integration and runtime flow.

Key design notes
- The adapter (`msf_lateral_movement/service.py`) intentionally reuses the central, shared service at `incalmo/core/services/metasploit_service.py` to perform the low-level msfrpc operations. This keeps Metasploit RPC logic centralized and avoids duplicated code.
- The LLM agent (`msf_lateral_movement/agent.py`) expects the adapter to implement: `connect()` (adapter constructs/uses shared client on init), `run_exploit_module()`, `run_auxiliary_module()`, `run_post_module()`, `run_command_on_session()`, and `list_sessions()` — these are provided by the adapter and backed by the core service.
- Configuration for Metasploit lives in `config/attacker_config.py` (the `MetasploitConfig` model). The agent's factory (`from_params`) reads `environment_state_service.metasploit_config` if present and passes it to the adapter.

Steps before Testing
- View the adapter: [incalmo/core/actions/HighLevel/llm_agents/msf_lateral_movement/service.py](incalmo/core/actions/HighLevel/llm_agents/msf_lateral_movement/service.py)
- View the agent: [incalmo/core/actions/HighLevel/llm_agents/msf_lateral_movement/agent.py](incalmo/core/actions/HighLevel/llm_agents/msf_lateral_movement/agent.py)
- Verify configuration in: [config/attacker_config.py](config/attacker_config.py)
- The project already includes `pymetasploit3` in `pyproject.toml`; ensure that dependency is installed before running.

How to test manually (quick)
1. Ensure `msfrpcd` (Metasploit RPC daemon) is running and reachable from the environment, or set `metasploit` config to point to your rpcd endpoint.
2. Install Python deps (from repo root):
```bash
pip install -e .
pip install pymetasploit3
```
3. Run the specific unit or integration tests, or run the app and exercise the lateral-move high-level action that uses the agent.

Troubleshooting
- If connections fail, check `config/attacker_config.py` `metasploit` section and verify host, port, password, and ssl settings.
- The adapter delegates to `incalmo/core/services/metasploit_service.py`. If that file changes, the adapter will continue to construct the core service using (`password, server, port, ssl`) and use `self._core.client` for operations.
