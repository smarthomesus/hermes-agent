from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from gateway import feedback_lifecycle as life
from hermes_cli.plugins import get_plugin_manager,PluginManager,PluginContext,PluginManifest

@pytest.fixture
def provider(monkeypatch):
    p=SimpleNamespace(stage=Mock(return_value=('trusted feedback',object())),commit=Mock(),release=Mock())
    monkeypatch.setattr(get_plugin_manager(),'_feedback_providers',{'telegram':p})
    return p

@pytest.mark.parametrize('commit',[True,False])
def test_pinned_exact_once(provider,commit):
    notes=[];lease=life.stage_feedback('telegram',source=SimpleNamespace(chat_id='peer'),config=None,append_note=notes.append)
    get_plugin_manager()._feedback_providers.clear()
    if commit:lease.commit()
    lease.release();lease.release()
    assert notes==['trusted feedback']
    assert provider.commit.call_count==int(commit)
    assert provider.release.call_count==int(not commit)

def test_publish_failure_releases(provider):
    def fail(note):raise RuntimeError('failed')
    assert life.stage_feedback('telegram',source=None,config=None,append_note=fail) is None
    provider.release.assert_called_once()

def test_missing_never_authority(monkeypatch):
    monkeypatch.setattr(get_plugin_manager(),'_feedback_providers',{})
    assert life.stage_feedback('telegram',source=None,config=None,append_note=Mock()) is None
    assert not life.feedback_bot_authored('telegram','peer','mid')

def test_registration_load_rollback(tmp_path):
    root=tmp_path/'feedback-example';root.mkdir()
    (root/'__init__.py').write_text("class P:\n def configure(self,*a,**k):pass\n record_sent=receive=stage=commit=release=is_bot_authored=reaction_delta=configure\ndef register(ctx):\n ctx.register_feedback_provider('telegram',P())\n raise RuntimeError('failed load')\n")
    m=PluginManager();m._load_plugin(PluginManifest(name='feedback-example',key='feedback-example',path=str(root),source='user'))
    assert m._plugins['feedback-example'].error
    assert not m._feedback_providers

def test_turn_wiring_has_finally_and_generation():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[2]/'gateway/run_turn.py').read_text()
    assert 'feedback_lease.commit()' in text
    assert 'if not event.internal:' in text
    assert 'feedback_lease.release()' in text[text.index('        finally:'):]


def test_source_is_copied_and_invalid_note_released(provider):
    source = SimpleNamespace(chat_id='original')
    def mutate(**kwargs):
        kwargs['source'].chat_id = 'changed'
        return 42, object()
    provider.stage.side_effect = mutate
    notes = []
    assert life.stage_feedback('telegram', source=source, config=None, append_note=notes.append) is None
    assert source.chat_id == 'original'
    assert not notes
    provider.release.assert_called_once()


@pytest.mark.parametrize('fails', [False, True])
def test_native_media_receipt_only_after_send(provider, fails):
    import ast, asyncio
    from pathlib import Path
    from unittest.mock import AsyncMock
    source = Path(__file__).resolve().parents[2]/'plugins/platforms/telegram/adapter.py'
    node = next(n for n in ast.parse(source.read_text()).body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == '_feedback_native_call')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    provider.record_sent = Mock()
    send = AsyncMock(return_value=[SimpleNamespace(message_id='media-mid', caption='caption')])
    if fails:
        send.side_effect = RuntimeError('transport failed')
        with pytest.raises(RuntimeError):
            asyncio.run(namespace['_feedback_native_call'](send, chat_id='peer'))
        provider.record_sent.assert_not_called()
    else:
        asyncio.run(namespace['_feedback_native_call'](send, chat_id='peer'))
        provider.record_sent.assert_called_once_with('peer', 'media-mid', 'caption')
