"""Outbound-only Telegram adapter with a fixed locally stored recipient."""
import json
from pathlib import Path
from urllib import error, request

class TelegramError(RuntimeError): pass
class TelegramSender:
    def __init__(self, token_path=Path('/home/santiago/.local/state/mail-agent/telegram/bot_token'), chat_id_path=Path('/home/santiago/.local/state/mail-agent/telegram/chat_id'), opener=request.urlopen):
        self._token=token_path.read_text().strip(); self._chat_id=chat_id_path.read_text().strip(); self._opener=opener
        if not self._token or not self._chat_id: raise TelegramError('missing configured recipient')
    def send_text(self, text):
        payload=json.dumps({'chat_id':self._chat_id,'text':text,'disable_web_page_preview':True}).encode()
        req=request.Request(f'https://api.telegram.org/bot{self._token}/sendMessage',data=payload,headers={'Content-Type':'application/json'})
        try:
            with self._opener(req,timeout=15) as response: data=json.loads(response.read())
        except (error.HTTPError,error.URLError,TimeoutError,json.JSONDecodeError) as exc: raise TelegramError(type(exc).__name__) from exc
        if not data.get('ok'): raise TelegramError('telegram_api_not_ok')

def format_notification(row):
    heading='⚠️ REVISIÓN' if row['importance']=='REVISION' else '🚨 IMPORTANTE'
    return f"{heading}\nCategoría: {row['category']}\nPrioridad: {row['priority']}\nRemitente: {row['sender'] or '—'}\nAsunto: {row['subject'] or '—'}\nResumen: {row['summary']}\nAcción sugerida: {row['suggested_action'] or 'Revisar'}"

def send_pending_notifications(store, sender):
    result={'sent':0,'failed':0}
    for row in store.claim_notifications():
        try: sender.send_text(format_notification(row))
        except TelegramError as exc: store.mark_notification_failed(row['id'],str(exc)); result['failed']+=1
        else: store.mark_notification_sent(row['id']); result['sent']+=1
    return result
