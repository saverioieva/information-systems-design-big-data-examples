"""Each role persists its state/inbox/outbox in a local SQLite DB."""
import json
import os
import sqlite3
from contextlib import contextmanager
from uuid import uuid4

class SQLiteTransaction:
    def __init__(self,db): self.db=db
    def seen(self,mid): return self.db.execute('SELECT 1 FROM inbox WHERE event_id=?',(mid,)).fetchone() is not None
    def mark_seen(self,mid):self.db.execute('INSERT INTO inbox(event_id) VALUES (?)',(mid,))
    def enqueue(self,route,order_id,**payload):
        mid=str(uuid4())
        message={'messageId':mid,'orderId':order_id,**payload}
        self.db.execute('INSERT INTO outbox(event_id,routing_key,payload) VALUES (?,?,?)',
                        (mid,route,json.dumps(message)))
    def create_order(self,oid,cid,amount):
        self.db.execute('INSERT INTO orders(order_id,customer_id,amount,status) VALUES (?,?,?,?)',
                        (oid,cid,amount,'APPROVAL_PENDING'))
        self.db.execute('INSERT INTO sagas(order_id,stage) VALUES (?,?)',(oid,'VERIFY_CONSUMER'))
    def get_order(self,oid):
        row=self.db.execute("""SELECT o.order_id,o.status,o.customer_id,o.amount,s.stage
                               FROM orders o JOIN sagas s USING(order_id) WHERE o.order_id=?""",(oid,)).fetchone()
        return dict(row) if row else None
    def get_stage(self,oid):
        row=self.db.execute('SELECT stage FROM sagas WHERE order_id=?',(oid,)).fetchone()
        return row['stage'] if row else None
    def set_stage(self,oid,stage):
        self.db.execute('UPDATE sagas SET stage=?,updated_at=CURRENT_TIMESTAMP WHERE order_id=?',(stage,oid))
        if stage in ('APPROVED','REJECTED'):
            self.db.execute('UPDATE orders SET status=? WHERE order_id=?',(stage,oid))
    def amount(self,oid):
        row=self.db.execute('SELECT amount FROM orders WHERE order_id=?',(oid,)).fetchone()
        if row is None:raise ValueError('Unknown order')
        return float(row['amount'])
    def create_ticket(self,oid):
        self.db.execute("INSERT OR IGNORE INTO tickets(order_id,state) VALUES (?, 'CREATE_PENDING')",(oid,))
    def update_ticket(self,oid,state):
        self.db.execute('UPDATE tickets SET state=? WHERE order_id=?',(state,oid))
    def authorize_card(self,oid,status):
        self.db.execute('INSERT OR REPLACE INTO authorizations(order_id,status) VALUES (?,?)',(oid,status))

class SqliteSagaStore:
    def __init__(self,role,db_file):self.role,self.db_file=role,db_file
    @contextmanager
    def transaction(self):
        con=sqlite3.connect(self.db_file,timeout=30)
        con.row_factory=sqlite3.Row
        try:
            con.execute('PRAGMA busy_timeout=30000')
            con.execute('BEGIN IMMEDIATE')
            yield SQLiteTransaction(con)
            con.commit()
        except Exception:
            con.rollback();raise
        finally:con.close()
    def initialize(self):
        os.makedirs(os.path.dirname(self.db_file) or '.',exist_ok=True)
        with self.transaction() as tx:
            c=tx.db
            c.execute('CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY,received_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            c.execute("""CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY,routing_key TEXT NOT NULL,
                         payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0)""")
            if self.role=='orchestrator':
                c.execute('CREATE TABLE IF NOT EXISTS orders(order_id TEXT PRIMARY KEY,customer_id TEXT NOT NULL,amount REAL NOT NULL,status TEXT NOT NULL)')
                c.execute('CREATE TABLE IF NOT EXISTS sagas(order_id TEXT PRIMARY KEY,stage TEXT NOT NULL,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            if self.role=='kitchen':c.execute('CREATE TABLE IF NOT EXISTS tickets(order_id TEXT PRIMARY KEY,state TEXT NOT NULL)')
            if self.role=='accounting':c.execute('CREATE TABLE IF NOT EXISTS authorizations(order_id TEXT PRIMARY KEY,status TEXT NOT NULL)')
    def pending(self):
        with self.transaction() as tx:
            row=tx.db.execute('SELECT event_id,routing_key,payload FROM outbox WHERE sent=0 ORDER BY rowid LIMIT 1').fetchone()
            return dict(row) if row else None
    def mark_sent(self,event_id):
        with self.transaction() as tx:tx.db.execute('UPDATE outbox SET sent=1 WHERE event_id=?',(event_id,))
