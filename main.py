import json
import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_fix_inconsistent_message", "Abyss AI", "0.1.0",
          "Re-sends the correct assistant text that precedes a generate_image tool call.")
class FixInconsistentMessage(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._conversation_ref = None
        self._send_count = 0
        self._has_tool_call = False
        logger.info("⚠️补救⚠️ Plugin loaded successfully.")

    @filter.on_llm_request()
    async def on_request(self, event: AstrMessageEvent, req):
        """Store conversation reference and reset state."""
        self._conversation_ref = getattr(req, "conversation", None)
        self._send_count = 0
        self._has_tool_call = False

    @filter.on_decorating_result()
    async def on_decorating(self, event: AstrMessageEvent):
        """Track if this interaction involves a tool call (2+ sends = agent loop)."""
        self._send_count += 1

    @filter.after_message_sent()
    async def after_sent(self, event: AstrMessageEvent):
        """After final send, wait for persistence then read correct text from history."""
        if self._send_count < 2:
            return  # Not an agent loop interaction, skip

        # Only act once per interaction (on the last after_message_sent)
        if self._has_tool_call:
            return
        self._has_tool_call = True

        conv = self._conversation_ref
        if not conv:
            return

        # Schedule delayed read to let runner persist to conv.history
        asyncio.create_task(self._delayed_echo(event, conv))

    async def _delayed_echo(self, event: AstrMessageEvent, conv):
        """Wait for runner to persist, then find and send correct text."""
        await asyncio.sleep(3)

        history_raw = getattr(conv, "history", None)
        if not history_raw:
            logger.warning("⚠️补救⚠️ conv.history empty after delay.")
            return

        try:
            messages = json.loads(history_raw) if isinstance(history_raw, str) else history_raw
        except json.JSONDecodeError:
            logger.error("⚠️补救⚠️ Failed to parse conv.history after delay.")
            return

        if not isinstance(messages, list):
            logger.warning(f"⚠️补救⚠️ Parsed history is not list: {type(messages).__name__}")
            return

        logger.info(f"⚠️补救⚠️ Delayed read: history len={len(messages)}")

        # Search from end for assistant message with generate_image
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "")
            tool_calls = msg.get("tool_calls", None)

            if role != "assistant" or not tool_calls:
                continue

            has_gen_image = False
            for tc in tool_calls:
                if isinstance(tc, dict):
                    fn_name = tc.get("function", {}).get("name", "")
                    if fn_name == "generate_image":
                        has_gen_image = True
                        break

            if not has_gen_image:
                continue

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

            logger.info(f"⚠️补救⚠️ FOUND after delay. text={repr(text[:120]) if text else 'EMPTY'}")

            if text and text.strip():
                await event.send(event.plain_result(text.strip()))
                logger.info("⚠️补救⚠️ Correct text sent.")
            else:
                logger.warning("⚠️补救⚠️ Found msg but text empty.")
            return

        logger.info("⚠️补救⚠️ No generate_image found in history after delay.")
