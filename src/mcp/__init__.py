# src/mcp — Rosetta MCP Server package
# Provides a Model Context Protocol interface to the Rosetta astrological engine.
#
# Architecture (5-stage pipeline):
#   1. Intent Router   — question → topic + relevant factors
#   2. Reading Engine   — factors + chart → ReadingPacket (hard-coded logic, zero LLM)
#   3. Reading Packet   — structured astrological facts ready for serialization
#   4. Prompt Builder   — ReadingPacket → compact system+user prompt
#   5. Prose Synthesizer— thin LLM wrapper that turns structured data into prose
