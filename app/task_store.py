"""Unified tasks, per-day completions, and reversible rewards. Legacy files untouched."""
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

def timestamp():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')

def time_delta_seconds(first,last):
    try:
        values=[datetime.fromisoformat(value) for value in (first,last)]
        values=[value if value.tzinfo else value.replace(tzinfo=timezone(timedelta(hours=8))) for value in values]
        return max(0,(values[1]-values[0]).total_seconds())
    except (TypeError,ValueError): return 0

def timer_day(task,day):
    return day if task.get('repeat') else task.get('timer_day') or next(iter(task.get('start_log',{})),day)

def timer_state(task,day,at=None):
    key=timer_day(task,day); record=task.get('timer_log',{}).get(key)
    start=task.get('start_log',{}).get(key) or (task.get('started_at') if not task.get('repeat') else None)
    end=task.get('completed_at'); now=at or timestamp()
    if record:
        seconds=max(0,record.get('accumulated_seconds',0))
        if record.get('running_since'): seconds+=time_delta_seconds(record['running_since'],end or now)
        return dict(started=True,seconds=seconds,paused=bool(record.get('paused')),finished=bool(record.get('finished')),tracked=True)
    return dict(started=bool(start),seconds=time_delta_seconds(start,end or now) if start else 0,paused=False,finished=bool(end),tracked=False)

def ensure_timer(task,day):
    key=timer_day(task,day); records={k:dict(v) for k,v in task.get('timer_log',{}).items()}
    if key not in records:
        start=task.get('start_log',{}).get(key) or (task.get('started_at') if not task.get('repeat') else None)
        if not start: raise ValueError('请先开始任务')
        records[key]=dict(accumulated_seconds=0,running_since=start,paused=False,finished=False)
    task['timer_log']=records
    if not task.get('repeat'): task['timer_day']=key
    return key,records[key]

def crop_status(task, day, completed=False, now=None):
    if completed: return 'harvested'
    zone=timezone(timedelta(hours=8))
    now=now or datetime.now(zone)
    if now.tzinfo is None: now=now.replace(tzinfo=zone)
    def local_time(value):
        parsed=datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=zone)
    deadline=task.get('deadline_time') if task.get('repeat') else task.get('deadline')
    if deadline:
        try:
            target=local_time(day+'T'+deadline if task.get('repeat') else deadline)
            if now>target: return 'late'
        except ValueError: pass
    started=(task.get('start_log') or {}).get(day)
    if started and task.get('minutes',0)>0:
        try:
            if now>local_time(started)+timedelta(minutes=task['minutes']): return 'late'
        except ValueError: pass
    return 'fresh'

ROOT = Path(__file__).parent

def minutes(value):
    if isinstance(value, (int, float)):
        return max(0, round(value))
    match = re.search(r'(\d+(?:\.\d+)?)', str(value or ''))
    if not match:
        return 0
    number = float(match[1]); text = str(value).lower()
    return round(number * (2400 if '周' in text else 480 if '天' in text else 60 if 'h' in text or '小时' in text else 1))

def due(task, day):
    if not task.get('enabled', True) or task.get('start', day) > day:
        return False
    d = date.fromisoformat(day)
    repeat = task.get('repeat', '')
    return (not repeat or repeat == 'daily' or
            repeat == 'weekly' and d.isoweekday() in task.get('weekdays', []) or
            repeat == 'monthly' and d.day in task.get('month_days', []))

class TaskStore:
    def __init__(self, root=ROOT):
        self.root = Path(root); (self.root / 'config').mkdir(exist_ok=True, parents=True)
        self.path = self.root / 'config' / 'task_world.db'
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS completions(task_id TEXT, day TEXT, snapshot TEXT NOT NULL,
                PRIMARY KEY(task_id,day)); CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);''')
            db.execute('CREATE TABLE IF NOT EXISTS templates(id TEXT PRIMARY KEY,data TEXT NOT NULL)')
            if not db.execute("SELECT 1 FROM settings WHERE key='imported'").fetchone():
                self.import_legacy(db)
                db.execute("INSERT INTO settings VALUES('imported','yes')")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def import_legacy(self, db):
        legacy_db = self.root / 'config' / 'todos.db'
        if legacy_db.exists():
            old = sqlite3.connect(legacy_db)
            try:
                old.row_factory = sqlite3.Row
                todos = [dict(r) for r in old.execute('SELECT * FROM todos')]
            finally:
                old.close()
            for t in todos:
                for key in ('attachments', 'follow_up_history'):
                    if isinstance(t.get(key), str):
                        t[key] = json.loads(t[key] or '[]')
        else:
            p = self.root / 'config' / 'todos.json'
            todos = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
        for old in todos:
            t = dict(old, id='todo:' + str(old['id']), repeat='', minutes=minutes(old.get('estimated_time')),
                     start=str(old.get('created_at') or date.today())[:10], enabled=True)
            self._save(db, t)
            if old.get('completed'):
                day = str(old.get('completed_at') or old.get('created_at') or date.today())[:10]
                self._receipt(db, t, day)
        p = self.root / 'config' / 'routines.json'
        for old in json.loads(p.read_text(encoding='utf-8')) if p.exists() else []:
            t = dict(old, id='routine:' + str(old['id']), minutes=minutes(old.get('estimated_time')),
                     priority=old.get('priority', '中'), start=str(old.get('created_at') or date.today())[:10])
            self._save(db, t)
            for day, record in old.get('check_log', {}).items():
                if record.get('done'): self._receipt(db, t, day)

    def _save(self, db, task):
        db.execute('INSERT OR REPLACE INTO tasks VALUES(?,?)', (task['id'], json.dumps(task, ensure_ascii=False)))

    def save(self, task):
        with self.connect() as db:
            row=db.execute('SELECT data FROM tasks WHERE id=?',(task['id'],)).fetchone()
            current=json.loads(row[0]) if row else {}
            saved=dict(task)
            # Editors may have stale copies. Never erase a recorded creation/start time.
            if row:
                saved['created_at']=current.get('created_at')
                saved['start_log']={**saved.get('start_log',{}),**current.get('start_log',{})}
                saved['timer_log']={**saved.get('timer_log',{}),**current.get('timer_log',{})}
                if current.get('timer_day'): saved['timer_day']=current['timer_day']
                if current.get('started_at'): saved['started_at']=current['started_at']
            else: saved['created_at']=task.get('created_at') or timestamp()
            self._save(db,saved)
        task.update(saved)

    def start_task(self,task_id,day):
        date.fromisoformat(day)
        with self.connect() as db:
            row=db.execute('SELECT data FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row: raise ValueError('任务不存在')
            if db.execute('SELECT 1 FROM completions WHERE task_id=? AND day=?',(task_id,day)).fetchone():
                raise ValueError('该次任务已经完成，不能重新开始')
            task=json.loads(row[0]); log=dict(task.get('start_log',{})); key=timer_day(task,day); log.setdefault(key,timestamp())
            if not due(task,day) or (not task.get('repeat') and db.execute('SELECT 1 FROM completions WHERE task_id=?',(task_id,)).fetchone()):
                raise ValueError('任务未启用、尚未到开始日期或已经完成')
            task['start_log']=log
            if not task.get('repeat'): task.setdefault('started_at',log[key])
            ensure_timer(task,day)
            self._save(db,task)
        return task

    def pause_task(self,task_id,day,paused=True):
        with self.connect() as db:
            row=db.execute('SELECT data FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row: raise ValueError('任务不存在')
            task=json.loads(row[0])
            if db.execute('SELECT 1 FROM completions WHERE task_id=? AND (day=? OR ?)',(task_id,day,not bool(task.get('repeat')))).fetchone():
                raise ValueError('已完成的任务不能改变计时')
            key,record=ensure_timer(task,day); now=timestamp()
            if paused and record.get('running_since'):
                record['accumulated_seconds']=timer_state(task,day,now)['seconds']; record['running_since']=None
                record['paused']=True; record['paused_at']=now
            elif not paused and (record.get('paused') or record.get('finished')):
                record['running_since']=now; record['paused']=False; record['resumed_at']=now; record['finished']=False
            self._save(db,task)
        return task

    def tasks(self):
        with self.connect() as db: return [json.loads(r[0]) for r in db.execute('SELECT data FROM tasks')]

    def _receipt(self, db, task, day):
        db.execute('INSERT OR IGNORE INTO completions VALUES(?,?,?)', (task['id'], day, json.dumps(task, ensure_ascii=False)))

    def completed(self):
        with self.connect() as db:
            return [(tid, day, json.loads(data)) for tid, day, data in db.execute('SELECT * FROM completions ORDER BY day DESC')]

    def toggle(self, task, day):
        with self.connect() as db:
            exists = db.execute('SELECT 1 FROM completions WHERE task_id=? AND day=?', (task['id'],day)).fetchone()
            if exists:
                db.execute('DELETE FROM completions WHERE task_id=? AND day=?', (task['id'],day))
                row=db.execute('SELECT data FROM tasks WHERE id=?',(task['id'],)).fetchone()
                if row:
                    live=json.loads(row[0]); key=timer_day(live,day)
                    if key in live.get('timer_log',{}):
                        _,record=ensure_timer(live,day); record.update(running_since=None,paused=True,finished=False)
                        self._save(db,live)
            else:
                row=db.execute('SELECT data FROM tasks WHERE id=?',(task['id'],)).fetchone()
                if not row: raise ValueError('任务不存在')
                snapshot=json.loads(row[0]); snapshot['completed_at']=timestamp()
                snapshot['started_at']=snapshot.get('start_log',{}).get(day) or (snapshot.get('started_at') if not snapshot.get('repeat') else None)
                key=timer_day(snapshot,day)
                if key in snapshot.get('timer_log',{}):
                    _,record=ensure_timer(snapshot,day); record['accumulated_seconds']=timer_state(snapshot,day,snapshot['completed_at'])['seconds']
                    record.update(running_since=None,paused=False,finished=True)
                    live=dict(snapshot); live.pop('completed_at',None); self._save(db,live)
                self._receipt(db,snapshot,day)

    def today(self, day):
        receipts = self.completed(); ever = {tid for tid,_,_ in receipts}; done = {tid for tid,d,_ in receipts if d==day}
        return [(t, t['id'] in done) for t in self.tasks() if due(t, day) and
                (t.get('repeat') or t['id'] not in ever or t['id'] in done)]

    def setting(self, key, default):
        with self.connect() as db: row = db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self.connect() as db: db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,str(value)))

    def templates(self):
        with self.connect() as db: return [json.loads(r[0]) for r in db.execute('SELECT data FROM templates')]

    def save_template(self,template):
        if not template.get('title','').strip(): raise ValueError('请填写模板名称')
        with self.connect() as db:
            row=db.execute('SELECT data FROM templates WHERE id=?',(template['id'],)).fetchone()
            saved=dict(template); saved['created_at']=json.loads(row[0]).get('created_at') if row else timestamp()
            saved['updated_at']=timestamp()
            db.execute('INSERT OR REPLACE INTO templates VALUES(?,?)',(saved['id'],json.dumps(saved,ensure_ascii=False)))
        template.update(saved)

def new_task():
    return dict(id=uuid.uuid4().hex, title='', priority='中', minutes=30, repeat='',
                start=date.today().isoformat(), weekdays=[], month_days=[], note='', attachments=[], enabled=True)
