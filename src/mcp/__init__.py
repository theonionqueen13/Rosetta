"""
Rosetta MCP Server package — Model Context Protocol interface.

Provides an AI-assisted astrological reading pipeline in five stages:

1. **Intent Router** — question → topic + relevant factors
2. **Reading Engine** — factors + chart → ReadingPacket (hard-coded, zero LLM)
3. **Reading Packet** — structured astrological facts ready for serialization
4. **Prompt Builder** — ReadingPacket → compact system + user prompt
5. **Prose Synthesizer** — thin LLM wrapper that turns structured data into prose
"""
