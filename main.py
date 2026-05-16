from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_fix_inconsistent_message", "Abyss AI", "0.1.0",
          "Re-sends the correct assistant text that precedes a generate_image tool call.")
class FixInconsistentMessage(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("⚠️补救⚠️ Plugin loaded successfully.")

    def _extract_text(self, resp) -> str | None:
        """Extract assistant text from LLMResponse via multiple fallback paths."""
        # Path 1: _completion_text
        text = getattr(resp, "_completion_text", None)
        if text and text.strip():
            return text.strip()

        # Path 2: raw_completion as OpenAI ChatCompletion object
        raw = getattr(resp, "raw_completion", None)
        if raw is None:
            return None

        try:
            content = raw.choices[0].message.content
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = [p["text"] for p in content if p.get("type") == "text"]
                joined = "\n".join(parts).strip()
                if joined:
                    return joined
        except (AttributeError, IndexError, KeyError, TypeError):
            pass

        # Path 3: raw_completion as dict
        if isinstance(raw, dict):
            try:
                content = raw["choices"][0]["message"].get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
                if isinstance(content, list):
                    parts = [p["text"] for p in content if p.get("type") == "text"]
                    joined = "\n".join(parts).strip()
                    if joined:
                        return joined
            except (KeyError, IndexError, TypeError):
                pass

        return None

    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, resp):
        """Debug: log every LLM response to see what's in resp."""
        tool_names = getattr(resp, "tools_call_name", None)
        completion_text = getattr(resp, "_completion_text", None)
        raw = getattr(resp, "raw_completion", None)

        logger.info(f"⚠️补救⚠️ on_llm_response fired. tools_call_name={tool_names}, "
                    f"_completion_text={repr(completion_text[:100]) if completion_text else None}, "
                    f"raw_completion type={type(raw).__name__}")

        # Log all attributes of resp for debugging
        attrs = [a for a in dir(resp) if not a.startswith("__")]
        logger.info(f"⚠️补救⚠️ resp attributes: {attrs}")

        if not tool_names or "generate_image" not in tool_names:
            return

        logger.info("⚠️补救⚠️ generate_image detected in tool_calls.")

        text = self._extract_text(resp)
        if text:
            logger.info(f"⚠️补救��️ Sending text: {text[:80]}...")
            await event.send(event.plain_result(text))
        else:
            logger.warning("⚠️补救⚠️ generate_image detected but no text extracted.")
