import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_fix_inconsistent_message", "Abyss AI", "0.1.0",
          "Re-sends the correct assistant text that precedes a generate_image tool call.")
class FixInconsistentMessage(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._last_echoed_tool_call_id = None
        logger.info("⚠️补救⚠️ Plugin loaded successfully.")

    @filter.on_llm_request()
    async def on_request(self, event: AstrMessageEvent, req):
        """On each new message, check contexts for un-echoed generate_image text."""
        contexts = getattr(req, "contexts", None)
        if not contexts or not isinstance(contexts, list):
            return

        # Search from end for most recent assistant msg with generate_image tool_call
        for msg in reversed(contexts):
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "")
            tool_calls = msg.get("tool_calls", None)

            if role != "assistant" or not tool_calls:
                continue

            # Find generate_image tool_call
            gen_image_tc_id = None
            for tc in tool_calls:
                if isinstance(tc, dict):
                    fn_name = tc.get("function", {}).get("name", "")
                    if fn_name == "generate_image":
                        gen_image_tc_id = tc.get("id", "")
                        break

            if not gen_image_tc_id:
                continue

            # Check if we already echoed this one
            if gen_image_tc_id == self._last_echoed_tool_call_id:
                return  # Already handled, stop

            # Extract text
            content = msg.get("content", "")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text_parts = []
                for p in content:
                    if isinstance(p, dict) and p.get("type") == "text":
                        text_parts.append(p.get("text", ""))
                text = "\n".join(text_parts)

            if text and text.strip():
                logger.info(f"⚠️补救⚠️ Echoing text for tool_call {gen_image_tc_id}: {text.strip()[:80]}...")
                await event.send(event.plain_result(text.strip()))
                self._last_echoed_tool_call_id = gen_image_tc_id
                logger.info("⚠️补救⚠️ Correct text sent.")
            else:
                logger.info(f"⚠️补救⚠️ Found tool_call {gen_image_tc_id} but text is empty, skipping.")
                self._last_echoed_tool_call_id = gen_image_tc_id

            return  # Only process the most recent one
