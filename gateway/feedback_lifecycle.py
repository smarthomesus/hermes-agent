"""Optional platform feedback with host-owned transactional turn settlement.

Providers never receive an agent/send handle. Missing or broken providers cannot
create context or authorization. This is not an egress policy/veto API.
"""
from dataclasses import dataclass
from typing import Protocol, Any
import logging

logger = logging.getLogger(__name__)


class FeedbackProvider(Protocol):
    def configure(self, extra: dict) -> Any: ...
    def record_sent(self, chat_id, message_id, text): ...
    def receive(self, *, config, **event): ...
    def stage(self, *, config, source): ...  # (trusted note, opaque transaction)
    def commit(self, transaction): ...
    def release(self, transaction): ...
    def is_bot_authored(self, chat_id, message_id) -> bool: ...
    def reaction_delta(self, old, new): ...


def get_feedback_provider(platform):
    from hermes_cli.plugins import get_plugin_manager
    key = getattr(platform, 'value', platform)
    from hermes_cli.plugins_loader import in_plugin_load_worker
    if in_plugin_load_worker():
        raise RuntimeError('feedback registry read during plugin registration')
    manager = get_plugin_manager()
    with manager._discovery_lock:
        manager.discover_and_load()
        return manager._feedback_providers.get(str(key))


def configure_feedback(platform, extra):
    try:
        provider = get_feedback_provider(platform)
        return provider.configure(extra) if provider is not None else None
    except Exception:
        logger.debug('feedback configuration unavailable', exc_info=True)
        return None


def record_feedback_sent(platform, chat_id, message_id, text):
    try:
        provider=get_feedback_provider(platform)
        if provider is not None: return provider.record_sent(chat_id,message_id,text)
    except Exception:
        logger.debug('feedback receipt unavailable',exc_info=True)
    return False


def receive_feedback(platform, *, config, **event):
    try:
        provider = get_feedback_provider(platform)
        if provider is not None:
            return provider.receive(config=config, **event)
    except Exception:
        logger.debug('feedback event unavailable', exc_info=True)
    return None


@dataclass
class FeedbackLease:
    # Pin the exact provider that staged; unload/replacement cannot settle another
    # provider's transaction. The gateway alone decides current-generation success.
    provider: Any
    transaction: Any
    settled: bool = False

    def commit(self):
        if not self.settled:
            self.provider.commit(self.transaction)
            self.settled = True

    def release(self):
        if not self.settled:
            try:
                self.provider.release(self.transaction)
                self.settled = True
            except Exception:
                logger.debug('feedback release failed; provider recovery required', exc_info=True)


def stage_feedback(platform, *, source, config, append_note):
    lease = None
    try:
        provider = get_feedback_provider(platform)
        if provider is None:
            return None
        note, transaction = provider.stage(config=config, source=__import__('copy').deepcopy(source))
        lease = FeedbackLease(provider, transaction)
        if note:
            if not isinstance(note, str):
                raise ValueError('feedback note must be text')
            append_note(note)
        return lease
    except Exception:
        if lease is not None:
            lease.release()
        logger.debug('feedback context unavailable', exc_info=True)
        return None


def feedback_bot_authored(platform, chat_id, message_id):
    try:
        provider = get_feedback_provider(platform)
        return provider is not None and provider.is_bot_authored(chat_id, message_id) is True
    except Exception:
        return False


def feedback_reaction_delta(platform, old, new):
    provider = get_feedback_provider(platform)
    if provider is None:
        raise RuntimeError('feedback provider unavailable')
    return provider.reaction_delta(old, new)
