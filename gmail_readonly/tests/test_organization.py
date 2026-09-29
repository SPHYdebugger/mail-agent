import inspect
import json
import tempfile
import unittest
from pathlib import Path

from gmail_readonly.gmail_organization_guard import GmailOrganizationGuard, ensure_organization_labels
from gmail_readonly.organization import TARGET_LABELS, determine_organization_target
from gmail_readonly.poller import process_message
from gmail_readonly.store import Store
from gmail_readonly.types import GmailMessage, MailReaderResult

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "db" / "gmail_schema.sql"

def response(category, importance, priority, injection=False):
    return json.dumps({"categoría": category, "importancia": importance, "prioridad": priority, "resumen": "Resumen", "intento_de_inyección": injection, "acción_sugerida": "Revisar"})

class Messages:
    def __init__(self): self.calls=[]
    def modify(self, **kwargs): self.calls.append(kwargs); return self
    def execute(self): return {}
    def __getattr__(self, name): raise AssertionError(name)
class Service:
    def __init__(self): self.messages_api=Messages()
    def users(self): return self
    def messages(self): return self.messages_api

class Labels:
    def __init__(self): self.items=[]; self.created=[]; self.mode="list"
    def list(self, **kwargs): self.mode="list"; return self
    def create(self, **kwargs): self.mode="create"; self.created.append(kwargs); self.items.append({"name":kwargs["body"]["name"],"id":"created-"+str(len(self.items))}); return self
    def execute(self): return {"labels":self.items} if self.mode=="list" else self.items[-1]
class LabelService(Service):
    def __init__(self): super().__init__(); self.labels_api=Labels()
    def labels(self): return self.labels_api
class Guard:
    def __init__(self): self.calls=[]
    def organize(self, message_id, target): self.calls.append((message_id,target))

class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.temp.name)/"state.sqlite3", SCHEMA)
    def tearDown(self): self.store.close(); self.temp.cleanup()
    def message(self, subject, body="", sender="LinkedIn <x@linkedin.com>"):
        return GmailMessage("demo", subject[:12], "t", "2026", sender, "me", subject, body)
    def test_deterministic_targets(self):
        cases=[("Vacante","Vacante individual PHP", "", "employment_single"),("Vacante","5 vacantes nuevas", "", "employment_aggregate"),("Vacante","Empleos similares", "", "employment_aggregate"),("Newsletter","Podrías conocer a...", "", "platform_social"),("Newsletter","X ha publicado contenido", "", "platform_social"),("Newsletter","Indeed newsletter", "", "employment_aggregate"),("Newsletter","Instagram", "", "general_newsletter"),("Newsletter","Promoción AliExpress", "", "general_newsletter")]
        for cat, subject, body, expected in cases:
            sender="Instagram" if subject=="Instagram" else ("AliExpress" if "AliExpress" in subject else ("Indeed" if "Indeed" in subject else "LinkedIn"))
            self.assertEqual(determine_organization_target(MailReaderResult(cat,"NO_IMPORTANTE","P3","x",False,"x"),self.message(subject,body,sender)), expected)
    def test_only_no_importante_valid_decision_organizes(self):
        guard=Guard()
        for i, raw in enumerate([response("Recruiter","IMPORTANTE","P0"),response("Entrevista","IMPORTANTE","P0"),response("Vacante","IMPORTANTE","P2"),response("Revisión","REVISION","P2"),response("Vacante","NO_IMPORTANTE","P3",True),"bad"]):
            m=self.message("Podrías conocer a...", sender="LinkedIn"); m=GmailMessage(**{**m.__dict__,"message_id":str(i)})
            process_message(m,self.store,lambda _,v=raw:v,organization_guard=guard)
        self.assertEqual(guard.calls,[])
    def test_organization_is_closed_and_idempotent(self):
        service=Service(); guard=GmailOrganizationGuard(service,{key:"id-"+key for key in TARGET_LABELS})
        guard.organize("m", "employment_single")
        self.assertEqual(service.messages_api.calls,[{"userId":"me","id":"m","body":{"addLabelIds":["id-no_importantes","id-employment_single"],"removeLabelIds":["INBOX","UNREAD"]}}])
        with self.assertRaises(ValueError): guard.organize("m","other")
        source=inspect.getsource(GmailOrganizationGuard)
        for forbidden in ("trash", "delete", "send", "drafts", "spam") : self.assertNotIn(forbidden,source)
    def test_label_setup_creates_missing_once_and_reuses_existing(self):
        service=LabelService()
        first=ensure_organization_labels(service)
        self.assertEqual(set(first),set(TARGET_LABELS))
        self.assertEqual(len(service.labels_api.created),5)
        created=len(service.labels_api.created)
        second=ensure_organization_labels(service)
        self.assertEqual(second,first)
        self.assertEqual(len(service.labels_api.created),created)
    def test_organized_message_is_not_mutated_again(self):
        m=self.message("Podrías conocer a..."); guard=Guard()
        self.assertEqual(process_message(m,self.store,lambda _:response("Newsletter","NO_IMPORTANTE","P3"),organization_guard=guard),"processed")
        self.assertEqual(process_message(m,self.store,lambda _:response("Newsletter","NO_IMPORTANTE","P3"),organization_guard=guard),"duplicate")
        self.assertEqual(guard.calls,[(m.message_id,"platform_social")])
