from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("astrbot_plugin_fix_inconsistent_message", "Abyss AI", "0.1.0",
          "Re-sends the correct assistant text that precedes a generate_image tool call.")
class FixInconsistentMessage(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("⚠️补救⚠️ Plugin loaded successfully.")

    @filter.on_llm_request()
    async def on_request(self, event: AstrMessageEvent, req):
        """Debug: fires before each LLM call. Check if it fires in agent loop."""
        logger.info(f"⚠️补救⚠️ on_llm_request fired. req type={type(req).__name__}")
        # Log req attributes
        attrs = [a for a in dir(req) if not a.startswith("_")]
        logger.info(f"⚠️补救⚠️ req attrs: {attrs}")
        # Try to access messages/prompt
        if hasattr(req, "messages"):
            msgs = req.messages
            logger.info(f"⚠️补救⚠️ req.messages count={len(msgs) if msgs else 0}")
            if msgs:
                for i, m in enumerate(msgs[-3:]):
                    role = m.get("role", "?") if isinstance(m, dict) else getattr(m, "role", "?")
                    logger.info(f"⚠️补救⚠️ msg[{i}] role={role}")
        if hasattr(req, "prompt"):
            prompt = req.prompt
            if isinstance(prompt, list):
                logger.info(f"⚠️补救⚠️ req.prompt count={len(prompt)}")
                for i, m in enumerate(prompt[-3:]):
                    role = m.get("role", "?") if isinstance(m, dict) else getattr(m, "role", "?")
                    content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
                    content_preview = str(content)[:60] if content else ""
                    logger.info(f"⚠️补救⚠️ prompt[{i}] role={role} content={content_preview}")

    @filter.on_decorating_result()
    async def on_decorating(self, event: AstrMessageEvent):
        """Debug: fires before message is sent to QQ."""
        result = event.get_result()
        chain = result.chain if result else None
        logger.info(f"⚠️补救⚠️ on_decorating_result fired. chain={chain}")

    @filter.after_message_sent()
    async def after_sent(self, event: AstrMessageEvent):
        """Debug: fires after message is sent."""
        logger.info(f"⚠️补救⚠️ after_message_sent fired.")
