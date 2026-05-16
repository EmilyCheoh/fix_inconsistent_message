from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("fix_inconsistent_message", "Abyss AI", "0.1.0",
          "Re-sends the correct assistant text that precedes a generate_image tool call.")
class FixInconsistentMessage(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._pending_echo_text: str | None = None

    def _extract_text_from_resp(self, resp) -> str | None:
        """Extract assistant text from LLMResponse, with fallback to raw_completion."""
        # Try _completion_text first
        text = resp._completion_text
        if text and text.strip():
            return text.strip()

        # Fallback: parse from raw_completion (OpenAI ChatCompletion format)
        raw = resp.raw_completion
        if raw is None:
            return None

        try:
            # OpenAI SDK object: raw.choices[0].message.content
            message = raw.choices[0].message
            content = message.content
            if isinstance(content, str) and content.strip():
                return content.strip()
            # If content is a list of parts (multimodal format)
            if isinstance(content, list):
                text_parts = [p["text"] for p in content if p.get("type") == "text"]
                joined = "\n".join(text_parts).strip()
                if joined:
                    return joined
        except (AttributeError, IndexError, KeyError, TypeError):
            pass

        # Fallback: raw_completion might be a dict
        if isinstance(raw, dict):
            try:
                message = raw["choices"][0]["message"]
                content = message.get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
                if isinstance(content, list):
                    text_parts = [p["text"] for p in content if p.get("type") == "text"]
                    joined = "\n".join(text_parts).strip()
                    if joined:
                        return joined
            except (KeyError, IndexError, TypeError):
                pass

        return None

    @filter.on_llm_response()
    async def capture_pre_tool_text(self, event: AstrMessageEvent, resp):
        """When LLM responds with a generate_image tool call, store the accompanying text."""
        if resp.tools_call_name and "generate_image" in resp.tools_call_name:
            text = self._extract_text_from_resp(resp)
            if text:
                self._pending_echo_text = text
                logger.info(f"[fix_inconsistent_message] Captured: {text[:80]}...")
            else:
                self._pending_echo_text = None
                logger.warning("[fix_inconsistent_message] generate_image detected but no text found in response.")

    @filter.on_llm_tool_respond()
    async def echo_after_tool(self, event: AstrMessageEvent, tool, tool_args, tool_result):
        """After generate_image completes, send the stored text to the user."""
        if tool.name == "generate_image" and self._pending_echo_text:
            logger.info(f"[fix_inconsistent_message] Sending captured text to user.")
            await event.send(event.plain_result(self._pending_echo_text))
            self._pending_echo_text = None
