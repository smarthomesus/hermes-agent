"""Optional platform delivery transactions. Host owns settlement; no send handle."""
from dataclasses import dataclass, field
from threading import RLock
from typing import Any
import re

def delivery_api(platform='telegram'):
    from hermes_cli.plugins import get_plugin_manager
    from hermes_cli.plugins_loader import in_plugin_load_worker
    if in_plugin_load_worker():
        raise RuntimeError('delivery registry read during plugin registration')
    manager = get_plugin_manager()
    with manager._discovery_lock:
        manager.discover_and_load()
        provider = manager._delivery_transaction_providers.get(str(getattr(platform, 'value', platform)))
    if provider is None: raise RuntimeError('delivery transaction provider unavailable')
    return provider

@dataclass
class DeliveryLease:
    provider: Any
    transaction: Any
    body: str
    metadata: dict
    settled: bool=False
    outcome: str|None=None
    _lock: Any=field(default_factory=RLock,repr=False)
    def __getattr__(self,name): return getattr(self.transaction,name)
    def settle(self,outcome,message_ids=()):
        if outcome not in {'confirmed','failed_before_send','ambiguous_timeout'}: raise ValueError('invalid delivery outcome')
        with self._lock:
            if self.settled:return False
            # Latch before provider work: exceptions cannot revive consumed authority.
            self.settled=True;self.outcome=outcome
            try:return self.provider.settle(self.transaction,outcome,tuple(message_ids))
            except BaseException:
                # The pinned provider gets one fail-closed cancellation attempt.
                if outcome=='confirmed': self.provider.settle(self.transaction,'failed_before_send',())
                raise

def prepare_delivery(platform,context,body):
    provider=delivery_api(platform)
    prepared=provider.prepare(context,body)
    if prepared is None:return None
    if not isinstance(prepared,dict) or set(prepared)!={'body','metadata','transaction'}: raise ValueError('invalid prepared delivery')
    if not isinstance(prepared['body'],str) or not isinstance(prepared['metadata'],dict): raise ValueError('invalid prepared delivery fields')
    return DeliveryLease(provider,prepared['transaction'],prepared['body'],prepared['metadata'])

def validate_delivery_url(platform, url, *, cfg=None):
    try:
        return delivery_api(platform).validate_action_url(url, cfg=cfg)
    except Exception:
        return None, 'delivery_provider_unavailable'


def strip_delivery_controls(body):
    # Host-owned inert control-block sanitization survives a missing/broken plugin.
    text=str(body or '')
    for left,right in [('⟦','⟧'),('[',']'),('【','】'),('«','»'),('〔','〕')]:
        text=re.sub(re.escape(left)+r'\s*HERMES_CRON_DECISIONS\s*\{.*?\}\s*'+re.escape(right),'',text,flags=re.I|re.S)
        text=re.sub(re.escape(left)+r'\s*HERMES_CRON_DECISIONS\s*[^'+re.escape(right)+']*'+re.escape(right),'',text,flags=re.I|re.S)
    return text.strip()


def prepare_optional_delivery(platform, context, body):
    try:
        delivery_api(platform)
    except RuntimeError:
        return None
    return prepare_delivery(platform, context, body)
