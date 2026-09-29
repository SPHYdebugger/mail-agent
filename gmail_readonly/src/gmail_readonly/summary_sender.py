"""One-shot periodic summary generation; never reads Gmail or invokes mail_reader."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from .telegram_sender import TelegramError

MADRID=ZoneInfo('Europe/Madrid')

def summary_window(now=None):
    now=(now or datetime.now(MADRID)).astimezone(MADRID)
    hour=next((h for h in (21,16,12) if now.time() >= time(h)), None)
    if hour is None: return None
    end=now.replace(hour=hour,minute=0,second=0,microsecond=0)
    start=end.replace(hour={12:0,16:12,21:16}[hour],minute=0)
    return start,end,f'{end.date().isoformat()}-{hour:02d}'

def build_summary(store, account, start, end):
    rows=store.connection.execute("SELECT * FROM gmail_messages WHERE account_id=? AND processed_at>=? AND processed_at<? ORDER BY processed_at",(account,start.astimezone(ZoneInfo('UTC')).isoformat(),end.astimezone(ZoneInfo('UTC')).isoformat())).fetchall()
    label_counts={name:0 for name in ('Empleo - Vacantes plataformas','Empleo - Agrupados plataformas','Plataformas - Social','General - Newsletters')}
    for r in rows:
        if r['organization_label'] in label_counts: label_counts[r['organization_label']]+=1
    title=end.strftime('%H:%M'); period=f'{start:%H:%M}–{end:%H:%M}'
    if not rows: return f'📬 Resumen de correo — {title}\nNo se recibieron correos nuevos desde el resumen anterior.'
    important=[r for r in rows if r['importance'] in ('IMPORTANTE','REVISION')]
    lines=[f'📬 Resumen de correo — {title}',f'Periodo: {period}',f'Procesados: {len(rows)}',f'🚨 Importantes: {sum(r["importance"]=="IMPORTANTE" for r in rows)}',f'⚠️ Revisión: {sum(r["importance"]=="REVISION" for r in rows)}',f'✅ No importantes: {sum(r["importance"]=="NO_IMPORTANTE" for r in rows)}','', 'Organizados:']
    lines += [f'• {k}: {v}' for k,v in label_counts.items()]
    if important:
        lines += ['', 'IMPORTANTE / REVISIÓN']
        for i,r in enumerate(important,1):
            icon='⚠️' if r['importance']=='REVISION' else '🚨'
            lines += [f'{i}. {icon} {r["category"]} · {r["priority"]}',f'Remitente: {r["sender"]}',f'Asunto: {r["subject"]}',f'Resumen: {r["summary"]}',f'Acción: {r["suggested_action"]}']
    return '\n'.join(lines)

def send_summary_once(store, sender, account, now=None):
    window=summary_window(now)
    if window is None: return {'status':'not_scheduled'}
    start,end,key=window; scheduled=end.isoformat()
    if end.hour == 12:
        previous=store.connection.execute("SELECT scheduled_for FROM notification_outbox WHERE account_id=? AND notification_kind='daily_summary' AND status='sent' AND scheduled_for<? ORDER BY scheduled_for DESC LIMIT 1",(account,scheduled)).fetchone()
        if previous:
            start=datetime.fromisoformat(previous['scheduled_for']).astimezone(MADRID)
    with store.connection:
        row=store.connection.execute("SELECT * FROM notification_outbox WHERE account_id=? AND notification_kind='daily_summary' AND message_id=?",(account,key)).fetchone()
        if row and row['status']=='sent': return {'status':'already_sent'}
        text=build_summary(store,account,start,end)
        if row: store.connection.execute("UPDATE notification_outbox SET status='sending',summary=?,attempts=attempts+1,last_error=NULL WHERE id=?",(text,row['id'])); nid=row['id']
        else:
            nid=store.connection.execute("INSERT INTO notification_outbox(account_id,notification_kind,message_id,summary,scheduled_for,timezone,status,attempts) VALUES (?,?,?,?,?,?, 'sending',1)",(account,'daily_summary',key,text,scheduled,'Europe/Madrid')).lastrowid
    try: sender.send_text(text)
    except TelegramError as exc: store.mark_notification_failed(nid,str(exc)); return {'status':'failed'}
    store.mark_notification_sent(nid); return {'status':'sent','period':key}
