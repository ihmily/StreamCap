## 2025-05-14 - [Config Performance Optimization]
**Learning:** The `ConfigManager` was performing synchronous disk I/O on every configuration value lookup via `get_config_value`. While individually fast, these operations aggregate and block the event loop in an `asyncio` application, potentially causing micro-stutters in the UI.
**Action:** Implement memory caching in `ConfigManager` to ensure that subsequent reads are served from RAM, and only write-through to disk when settings are modified.
