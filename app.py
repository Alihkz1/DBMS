from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import json, sqlite3, re, os

PORT = 8000
DB_FILE = "app.db"
identifier_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
allowed_types = {"TEXT", "INTEGER"}

def valid_identifier(name):
    return bool(identifier_re.match(name))

def qi(name):
    return '"' + name.replace('"', '""') + '"'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def table_exists(conn, table):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None

def get_schema(conn, table):
    if not valid_identifier(table):
        return {"ok": False, "error": "invalid table name"}
    cur = conn.execute(f"PRAGMA table_info({qi(table)})")
    rows = cur.fetchall()
    cols = []
    pk_cols = []
    for r in rows:
        cols.append({"cid": r["cid"], "name": r["name"], "type": r["type"], "notnull": r["notnull"], "dflt_value": r["dflt_value"], "pk": r["pk"]})
        if r["pk"]:
            pk_cols.append(r["name"])
    key_mode = "none"
    key_field = None
    if len(pk_cols) == 1:
        key_mode = "pk"
        key_field = pk_cols[0]
    else:
        try:
            conn.execute(f"SELECT rowid FROM {qi(table)} LIMIT 1")
            key_mode = "rowid"
            key_field = "rowid"
        except sqlite3.DatabaseError:
            key_mode = "none"
            key_field = None
    return {"ok": True, "columns": cols, "key_mode": key_mode, "key_field": key_field}

def serve_file(handler, path):
    if path == "/":
        full_path = os.path.join("templates", "index.html")
    elif path.startswith("/static/"):
        full_path = os.path.join("static", path[len("/static/"):])
    elif path.startswith("/templates/"):
        full_path = os.path.join("templates", path[len("/templates/"):])
    else:
        full_path = os.path.join("templates", path.lstrip("/"))

    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            content = f.read()
        if full_path.endswith(".html"):
            handler.send_response(200)
            handler.send_header("Content-type", "text/html; charset=utf-8")
            handler.end_headers()
            handler.wfile.write(content)
        elif full_path.endswith(".css"):
            handler.send_response(200)
            handler.send_header("Content-type", "text/css")
            handler.end_headers()
            handler.wfile.write(content)
        elif full_path.endswith(".js"):
            handler.send_response(200)
            handler.send_header("Content-type", "application/javascript")
            handler.end_headers()
            handler.wfile.write(content)
        else:
            handler.send_response(200)
            handler.end_headers()
            handler.wfile.write(content)
    else:
        handler.send_response(404)
        handler.end_headers()
        handler.wfile.write(b"Not found")

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-type","application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path.startswith("/static/") or path.startswith("/templates/") or path=="/":
            serve_file(self, path)
        elif path=="/tables":
            conn = get_db()
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            items = [r["name"] for r in cur.fetchall()]
            conn.close()
            self._send_json({"ok": True, "tables": items})
        elif path.startswith("/schema/"):
            table = path[len("/schema/"):]
            conn = get_db()
            s = get_schema(conn, table)
            conn.close()
            self._send_json(s)
        elif path.startswith("/data/"):
            table = path[len("/data/"):]
            conn = get_db()
            s = get_schema(conn, table)
            if not s["ok"]:
                conn.close()
                self._send_json(s,400)
                return
            cols = [c["name"] for c in s["columns"]]
            key_mode = s["key_mode"]
            key_field = s["key_field"]
            select_cols = []
            if key_mode=="rowid":
                select_cols.append("rowid AS __key__")
            elif key_mode=="pk":
                select_cols.append(f"{qi(key_field)} AS __key__")
            else:
                select_cols.append("NULL AS __key__")
            select_cols.extend(qi(c) for c in cols)
            try:
                cur = conn.execute(f"SELECT {', '.join(select_cols)} FROM {qi(table)}")
                rows = [dict(r) for r in cur.fetchall()]
            except sqlite3.DatabaseError as e:
                conn.close()
                self._send_json({"ok": False, "error": str(e)},400)
                return
            conn.close()
            self._send_json({"ok": True, "key_mode": key_mode, "key_field": key_field, "columns": cols, "rows": rows})
        else:
            self.send_response(404)
            self.end_headers()
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length",0))
        raw = self.rfile.read(length)
        data = json.loads(raw) if raw else {}
        conn = get_db()
        if path=="/create_table":
            table = data.get("table")
            columns = data.get("columns", [])
            auto_id = data.get("auto_id", True)
            if not table or not valid_identifier(table):
                self._send_json({"ok": False, "error": "invalid table name"},400)
                return
            if not isinstance(columns,list) or len(columns)==0:
                self._send_json({"ok": False, "error": "at least one column is required"},400)
                return
            col_defs=[]
            seen=set()
            if auto_id:
                col_defs.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
                seen.add("id")
            for c in columns:
                name=c.get("name")
                typ=c.get("type","TEXT").upper()
                notnull=bool(c.get("notnull",False))
                if not name or not valid_identifier(name):
                    self._send_json({"ok": False, "error": "invalid column name"},400)
                    return
                if name in seen:
                    self._send_json({"ok": False, "error": "duplicate column name"},400)
                    return
                if typ not in allowed_types:
                    self._send_json({"ok": False, "error": "invalid column type"},400)
                    return
                seen.add(name)
                part=f'{qi(name)} {typ}'
                if notnull:
                    part+=" NOT NULL"
                col_defs.append(part)
            ddl=f'CREATE TABLE IF NOT EXISTS {qi(table)} ({", ".join(col_defs)})'
            try:
                conn.execute(ddl)
                conn.commit()
            except sqlite3.DatabaseError as e:
                conn.close()
                self._send_json({"ok": False, "error": str(e)},400)
                return
            conn.close()
            self._send_json({"ok": True})
        elif path.startswith("/insert/"):
            table = path[len("/insert/"):]
            s = get_schema(conn, table)
            if not s["ok"]:
                conn.close()
                self._send_json(s,400)
                return
            payload = data
            cols = [c["name"] for c in s["columns"]]
            pk = s["key_field"] if s["key_mode"]=="pk" else None
            insert_cols = []
            values=[]
            for k,v in payload.items():
                if not valid_identifier(k):
                    conn.close()
                    self._send_json({"ok": False, "error": "invalid column"},400)
                    return
                if k in cols and k!=pk:
                    insert_cols.append(qi(k))
                    values.append(v if v!="" else None)
            if len(insert_cols)==0:
                conn.close()
                self._send_json({"ok": False, "error": "no valid columns"},400)
                return
            placeholders=", ".join("?" for _ in insert_cols)
            sql=f"INSERT INTO {qi(table)} ({', '.join(insert_cols)}) VALUES ({placeholders})"
            try:
                conn.execute(sql, values)
                conn.commit()
            except sqlite3.DatabaseError as e:
                conn.close()
                self._send_json({"ok": False, "error": str(e)},400)
                return
            conn.close()
            self._send_json({"ok": True})
        elif path.startswith("/update/"):
             try:
                 parts = path[len("/update/"):].split("/",1)
                 if len(parts)!=2:
                     self._send_json({"ok": False, "error": "invalid path"},400)
                     return
                 table, key = parts
                 payload = data
                 s = get_schema(conn, table)
                 if not s["ok"]:
                     self._send_json(s,400)
                     return
                 cols = [c["name"] for c in s["columns"] if c["name"] != s["key_field"]]
                 set_clause = ", ".join(f'{qi(c)}=?' for c in cols)
                 values = [payload.get(c) for c in cols]
                 if s["key_mode"]=="pk":
                     where = f"{qi(s['key_field'])}=?"
                 else:
                     where = "rowid=?"
                 values.append(key)
                 sql = f"UPDATE {qi(table)} SET {set_clause} WHERE {where}"
                 conn.execute(sql, values)
                 conn.commit()
                 self._send_json({"ok": True})
             except Exception as e:
                 self._send_json({"ok": False, "error": str(e)},500)
             finally:
                 conn.close()
         
        else:
            self.send_response(404)
            self.end_headers()
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/delete/"):
            parts=path[len("/delete/"):].split("/",1)
            if len(parts)!=2:
                self.send_response(400)
                self.end_headers()
                return
            table,key=parts
            conn=get_db()
            s=get_schema(conn, table)
            if not s["ok"]:
                conn.close()
                self._send_json(s,400)
                return
            where=""
            values=[]
            if s["key_mode"]=="pk":
                where=f"WHERE {qi(s['key_field'])}=?"
                values.append(key)
            elif s["key_mode"]=="rowid":
                where="WHERE rowid=?"
                values.append(key)
            else:
                conn.close()
                self._send_json({"ok": False, "error": "no key available for delete"},400)
                return
            sql=f"DELETE FROM {qi(table)} {where}"
            try:
                conn.execute(sql, values)
                conn.commit()
            except sqlite3.DatabaseError as e:
                conn.close()
                self._send_json({"ok": False, "error": str(e)},400)
                return
            conn.close()
            self._send_json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

httpd = HTTPServer(("0.0.0.0", PORT), Handler)
print(f"Server running at http://127.0.0.1:{PORT}/")
httpd.serve_forever()