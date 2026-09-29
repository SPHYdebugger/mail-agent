import tempfile
import unittest
from pathlib import Path
from gmail_readonly.store import Store
from gmail_readonly.types import GmailMessage, MailReaderResult
from gmail_readonly.telegram_sender import TelegramError, format_notification, send_pending_notifications

ROOT=Path(__file__).resolve().parents[1]; SCHEMA=ROOT/'db'/'gmail_schema.sql'
class Sender:
    def __init__(self, fail=False): self.fail=fail; self.texts=[]
    def send_text(self,text):
        self.texts.append(text)
        if self.fail: raise TelegramError('http')
class TelegramTests(unittest.TestCase):
    def setUp(self): self.t=tempfile.TemporaryDirectory(); self.s=Store(Path(self.t.name)/'x.db',SCHEMA)
    def tearDown(self): self.s.close(); self.t.cleanup()
    def add(self, importance='IMPORTANTE', action='Revisar'):
        m=GmailMessage('a','m'+importance,'t','d','sender@example.com','me','Asunto','body')
        self.s.claim(m); self.s.mark_processed('a',m.message_id,MailReaderResult('Recruiter',importance,'P0' if importance=='IMPORTANTE' else 'P2','Resumen breve',False,action)); self.s.queue_immediate_alert('a',m.message_id)
    def test_success_is_sent_once_and_formats_important(self):
        self.add(action='Responder al recruiter'); sender=Sender(); self.assertEqual(send_pending_notifications(self.s,sender),{'sent':1,'failed':0}); self.assertIn('🚨 IMPORTANTE',sender.texts[0]); self.assertIn('Remitente: sender@example.com',sender.texts[0]); self.assertIn('Acción sugerida: Responder al recruiter',sender.texts[0]); self.assertEqual(send_pending_notifications(self.s,sender),{'sent':0,'failed':0})
    def test_failure_remains_retryable_and_revision_format(self):
        self.add('REVISION'); bad=Sender(True); self.assertEqual(send_pending_notifications(self.s,bad),{'sent':0,'failed':1}); self.assertEqual(self.s.outbox()[0]['status'],'failed'); good=Sender(); self.assertEqual(send_pending_notifications(self.s,good),{'sent':1,'failed':0}); self.assertIn('⚠️ REVISIÓN',good.texts[0])
