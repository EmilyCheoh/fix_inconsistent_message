import json
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
        logger.info("⚠️补救⚠️ Plugin loaded successfully.")

    @filter.on_llm_request()
    async def on_request(self, event: AstrMessageEvent, req):
        """Store conversation reference and reset send counter."""
        self._conversation_ref = getattr(req, "conversation", None)
        self._send_count = 0

    @filter.after_message_sent()
    async def after_sent(self, event: AstrMessageEvent):
        """After 2nd send (agent loop done), find tool_call text in context and send it."""
        self._send_count += 1

        if self._send_count < 2:
            return

        conv = self._conversation_ref
        if not conv:
            return

        history = getattr(conv, "history", None)
        if not history:
            logger.warning("⚠️补救⚠️ conv.history is empty/None.")
            return

        # Parse history — could be string (JSON) or list
        messages = None
        if isinstance(history, str):
            try:
                messages = json.loads(history)
                logger.info(f"⚠️补救⚠️ Parsed history as JSON string. type={type(messages).__name__}, len={len(messages) if isinstance(messages, list) else 'N/A'}")
            except json.JSONDecodeError as e:
                logger.error(f"⚠️补救⚠️ Failed to parse history as JSON: {e}")
                # Log first 200 chars to understand format
                logger.info(f"⚠️补救⚠️ history[:200] = {repr(history[:200])}")
                return
        elif isinstance(history, list):
            messages = history
            logger.info(f"⚠️补救⚠️ history is already a list, len={len(messages)}")
        else:
            logger.warning(f"⚠️补救⚠️ history is unexpected type: {type(history).__name__}")
            logger.info(f"⚠️补救⚠️ history repr[:200] = {repr(str(history))[:200]}")
            return

        if not isinstance(messages, list):
            logger.warning(f"⚠️补救⚠️ Parsed history is not a list: {type(messages).__name__}")
            return

        # Search from the end for assistant message with generate_image tool_call
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "")
            tool_calls = msg.get("tool_calls", None)

            if role != "assistant" or not tool_calls:
                continue

            # Check if any tool_call is generate_image
            has_gen_image = False
            for tc in tool_calls:
                fn_name = ""
                if isinstance(tc, dict):
                    fn_name = tc.get("function", {}).get("name", "")
                if fn_name == "generate_image":
                    has_gen_image = True
                    break

            if not has_gen_image:
                continue

            # Found it. Extract text from content.
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

            logger.info(f"⚠️补救⚠️ FOUND. text={repr(text[:120]) if text else 'EMPTY'}")

            if text and text.strip():
                await event.send(event.plain_result(text.strip()))
                logger.info("⚠️补救⚠️ Correct text sent to user.")
            else:
                logger.warning("⚠️补救⚠️ tool_call message found but text is empty.")
            return

        logger.info("⚠️补救⚠️ No assistant+generate_image message found in history.")
