from pathlib import Path
import sqlite3
import json
from urllib.parse import quote
from .safeos import open_regular
import os
import threading
from contextlib import contextmanager
from .domain import uid
from .paths import safe_name

class Catalog:
    def __init__(self,root):
        self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
        self.meta=self.root/'.片集'; self.meta.mkdir(exist_ok=True)
        self.lock=threading.RLock()
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS activities(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,folder TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS people(id TEXT PRIMARY KEY,activity_id TEXT NOT NULL,name TEXT NOT NULL,folder TEXT NOT NULL,role TEXT,embedding TEXT,UNIQUE(activity_id,name));
            CREATE TABLE IF NOT EXISTS photos(id TEXT PRIMARY KEY,activity_id TEXT NOT NULL,person_id TEXT NOT NULL,stem TEXT NOT NULL,captured_at TEXT,edited INTEGER DEFAULT 0,manual_person INTEGER DEFAULT 0,opened_at TEXT,primary_export_id TEXT,signature TEXT NOT NULL,UNIQUE(activity_id,signature));
            CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,photo_id TEXT NOT NULL,kind TEXT NOT NULL,path TEXT UNIQUE NOT NULL,sha256 TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,kind TEXT NOT NULL,phase TEXT NOT NULL,payload TEXT NOT NULL,error TEXT);
            CREATE TABLE IF NOT EXISTS detached_exports(id TEXT PRIMARY KEY,photo_id TEXT NOT NULL,path TEXT UNIQUE NOT NULL,sha256 TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS import_members(activity_id TEXT NOT NULL,kind TEXT NOT NULL,sha256 TEXT NOT NULL,photo_id TEXT NOT NULL,PRIMARY KEY(activity_id,kind,sha256,photo_id));
            CREATE TABLE IF NOT EXISTS trashed_photos(photo_id TEXT PRIMARY KEY,payload TEXT NOT NULL,deleted_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS purges(photo_id TEXT PRIMARY KEY,payload TEXT NOT NULL,error TEXT);
            CREATE TABLE IF NOT EXISTS deleted_activities(activity_id TEXT PRIMARY KEY);
            INSERT OR IGNORE INTO import_members SELECT p.activity_id,a.kind,a.sha256,p.id FROM assets a JOIN photos p ON p.id=a.photo_id WHERE a.kind IN ('jpeg','raw');
            ''')

    @contextmanager
    def connect(self):
        with self.lock:
            if hasattr(self,'guard'): self.guard()
            path=self.meta/'catalog.sqlite3'
            fd=open_regular(path); os.close(fd)
            db=sqlite3.connect('file:'+quote(str(path),safe='/')+'?mode=rw',uri=True,timeout=10)
            try:
                if hasattr(self,'guard'): self.guard()
                db.execute('PRAGMA synchronous=FULL')
                db.execute('PRAGMA trusted_schema=OFF')
                db.row_factory=sqlite3.Row
                yield db
                if hasattr(self,'guard'): self.guard()
                db.commit()
            except BaseException:
                db.rollback(); raise
            finally: db.close()

    def rows(self,sql,args=()):
        with self.connect() as db: return [dict(r) for r in db.execute(sql,args)]

    def activity(self,name):
        safe_name(name)
        existing=self.rows('SELECT * FROM activities WHERE name=?',(name,))
        if existing:
            if self.rows('SELECT activity_id FROM deleted_activities WHERE activity_id=?',(existing[0]['id'],)):
                raise ValueError('此活动已移入回收站，请先恢复其中的照片，或使用其他活动名称')
            return existing[0]
        ident=uid()
        with self.connect() as db:
            db.execute('INSERT INTO activities VALUES(?,?,?)',(ident,name,name))
            for person_name,role in [('合照','group'),('待分类','unclassified')]:
                db.execute('INSERT INTO people VALUES(?,?,?,?,?,NULL)',(uid(),ident,person_name,person_name,role))
        return self.rows('SELECT * FROM activities WHERE id=?',(ident,))[0]

    def activities(self): return self.rows('SELECT * FROM activities WHERE NOT EXISTS(SELECT 1 FROM deleted_activities d WHERE d.activity_id=activities.id) ORDER BY rowid DESC')
    def people(self,activity_id): return self.rows('SELECT * FROM people WHERE activity_id=? ORDER BY rowid',(activity_id,))

    def add_person(self,activity_id,name,role=None,embedding=None):
        safe_name(name)
        ident=uid()
        with self.connect() as db:
            db.execute('INSERT INTO people VALUES(?,?,?,?,?,?)',(ident,activity_id,name,name,role,json.dumps(embedding) if embedding is not None else None))
        return self.person(ident)

    def person(self,ident):
        rows=self.rows('SELECT * FROM people WHERE id=?',(ident,))
        if not rows: raise ValueError('人物不存在')
        return rows[0]

    def photos(self,activity_id=None,trashed=False):
        sql='SELECT * FROM photos WHERE '+('' if trashed else 'NOT ')+'EXISTS(SELECT 1 FROM trashed_photos t WHERE t.photo_id=photos.id)'; args=()
        if activity_id: sql+=' AND activity_id=?'; args=(activity_id,)
        rows=self.rows(sql+' ORDER BY captured_at, rowid',args)
        for p in rows: p['assets']=self.assets(p['id'])
        return rows

    def photo(self,ident,include_trashed=False):
        rows=self.rows('SELECT * FROM photos WHERE id=?',(ident,))
        if not rows: raise ValueError('照片不存在')
        if not include_trashed and self.rows('SELECT photo_id FROM trashed_photos WHERE photo_id=?',(ident,)):raise ValueError('照片在回收站中，请先恢复')
        p=rows[0]; p['assets']=self.assets(ident); return p

    def assets(self,photo_id): return self.rows('SELECT * FROM assets WHERE photo_id=? ORDER BY rowid',(photo_id,))

    def operation(self,ident):
        rows=self.rows('SELECT * FROM operations WHERE id=?',(ident,))
        if not rows: raise ValueError('操作不存在')
        r=rows[0]; r['payload']=json.loads(r['payload']); return r
