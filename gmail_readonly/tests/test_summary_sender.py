import tempfile, unittest
from datetime import datetime
from pathlib import Path
from gmail_readonly.store import Store
from gmail_readonly.summary_sender import MADRID, send_summary_once, summary_window
from gmail_readonly.telegram_sender import TelegramError
from gmail_readonly.types import GmailMessage, MailReaderResult
ROOT=Path(__file__).resolve().parents[1]; SCHEMA=ROOT/'db'/'gmail_schema.sql'
class Sender:
 def __init__(self,fail=False): self.fail=fail; self.messages=[]
 def send_text(self,t):
  self.messages.append(t)
  if self.fail: raise TelegramError('fail')
class Tests(unittest.TestCase):
 def setUp(self): self.t=tempfile.TemporaryDirectory(); self.s=Store(Path(self.t.name)/'x.db',SCHEMA)
 def tearDown(self): self.s.close(); self.t.cleanup()
 def add(self,importance='IMPORTANTE',label='Empleo - Vacantes plataformas'):
  m=GmailMessage('a','m'+importance,'t','d','x@example.com','me','Asunto',''); self.s.claim(m); self.s.mark_processed('a',m.message_id,MailReaderResult('Recruiter',importance,'P0' if importance=='IMPORTANTE' else 'P2','Resumen',False,'Revisar')); self.s.connection.execute("UPDATE gmail_messages SET processed_at=?,organization_label=? WHERE message_id=?",('2026-09-27T12:30:00+00:00',label,m.message_id)); self.s.connection.commit()
 def test_windows_and_data(self):
  self.add(); sender=Sender(); r=send_summary_once(self.s,sender,'a',datetime(2026,9,27,16,1,tzinfo=MADRID)); self.assertEqual(r['status'],'sent'); self.assertIn('12:00–16:00',sender.messages[0]); self.assertIn('Importantes: 1',sender.messages[0]); self.assertIn('Empleo - Vacantes plataformas: 1',sender.messages[0])
 def test_empty_and_idempotent(self):
  sender=Sender(); now=datetime(2026,9,27,12,1,tzinfo=MADRID); self.assertEqual(send_summary_once(self.s,sender,'a',now)['status'],'sent'); self.assertIn('No se recibieron',sender.messages[0]); self.assertEqual(send_summary_once(self.s,sender,'a',now)['status'],'already_sent'); self.assertEqual(len(sender.messages),1)
 def test_failure_retries(self):
  now=datetime(2026,9,27,21,1,tzinfo=MADRID); self.assertEqual(send_summary_once(self.s,Sender(True),'a',now)['status'],'failed'); self.assertEqual(send_summary_once(self.s,Sender(),'a',now)['status'],'sent')
