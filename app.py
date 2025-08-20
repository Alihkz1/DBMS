from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import json
import sqlite3
import re
import os

# پورت سرور
PORT = 8000
# فایل دیتابیس
DB_FILE = "app.db"
# الگوی نام‌های معتبر برای جدول و ستون‌ها
identifier_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# --------------------- توابع کمکی ---------------------

# بررسی اینکه نام جدول یا ستون معتبر باشد
def valid_identifier(name):
    return bool(identifier_re.match(name))

# "quote identifier" برای جلوگیری از SQL injection
def qi(name):
    return '"' + name.replace('"', '""') + '"'

# اتصال به دیتابیس
def get_db():
    return sqlite3.connect(DB_FILE)

# بررسی اینکه جدول موجود باشد
def table_exists(conn, table):
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None

# --------------------- توابع اسکیمای جدول ---------------------

# گرفتن اسکیمای جدول شامل ستون‌ها و کلید اصلی
def get_schema(conn, table):
    # اگر نام نامعتبر باشد یا جدول وجود نداشته باشد
    if not valid_identifier(table) or not table_exists(conn, table):
        return {"ok": False, "error": "invalid or missing table"}

    # گرفتن اطلاعات ستون‌ها
    cur = conn.execute(f"PRAGMA table_info({qi(table)})")
    cols = [{"cid": cid, "name": name, "type": ctype, "pk": pk}
            for cid, name, ctype, notnull, dflt, pk in cur.fetchall()]

    # تعیین کلید اصلی (اگر نداشت، از rowid استفاده می‌کنیم)
    key_field = next((c["name"] for c in cols if c["pk"]), "rowid")
    return {"ok": True, "table": table, "columns": cols, "key_field": key_field}

# گرفتن داده‌های جدول همراه با rowid
def get_data(conn, table):
    s = get_schema(conn, table)
    if not s["ok"]:
        return s

    # انتخاب همه ستون‌ها به همراه rowid
    cur = conn.execute(f"SELECT rowid, * FROM {qi(table)}")
    cols = ["rowid"] + [c["name"] for c in s["columns"]]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    return {"ok": True, "rows": rows, "schema": s}

# --------------------- سرویس فایل استاتیک ---------------------

def serve_file(handler, path):
    # مسیر پیش‌فرض صفحه اصلی
    if path == "/":
        full_path = os.path.join("frontend", "index.html")
    else:
        full_path = os.path.join("frontend", path.lstrip("/"))

    # اگر فایل وجود داشت
    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            content = f.read()
        # تعیین نوع محتوا بر اساس پسوند
        if full_path.endswith(".html"):
            handler.send_response(200)
            handler.send_header("Content-type", "text/html; charset=utf-8")
        elif full_path.endswith(".css"):
            handler.send_response(200)
            handler.send_header("Content-type", "text/css")
        elif full_path.endswith(".js"):
            handler.send_response(200)
            handler.send_header("Content-type", "application/javascript")
        else:
            handler.send_response(200)
        handler.end_headers()
        handler.wfile.write(content)
    else:
        # اگر فایل پیدا نشد
        handler.send_response(404)
        handler.end_headers()
        handler.wfile.write(b"Not found")

# --------------------- Handler درخواست‌ها ---------------------

class Handler(BaseHTTPRequestHandler):
    # ارسال پاسخ JSON
    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # دریافت GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # سرویس فایل‌های فرانت‌اند
        if path == "/" or path.endswith(".html") or path.endswith(".css") or path.endswith(".js"):
            serve_file(self, path)
            return

        try:
            conn = get_db()

            # لیست جدول‌ها
            if path == "/tables":
                cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                self._send_json({"ok": True, "tables": tables})

            # اسکیمای جدول
            elif path.startswith("/schema/"):
                table = path.split("/", 2)[-1]
                self._send_json(get_schema(conn, table))

            # داده‌های جدول
            elif path.startswith("/data/"):
                table = path.split("/", 2)[-1]
                if not table_exists(conn, table):
                    self._send_json({"ok": False, "error": "table not found"}, 404)
                else:
                    self._send_json(get_data(conn, table))

            else:
                serve_file(self, path)

        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)
        finally:
            conn.close()

    # دریافت POST
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # خواندن body درخواست
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length > 0 else "{}"
        try:
            payload = json.loads(body) if body else {}
        except:
            payload = {}

        try:
            conn = get_db()

            # ایجاد جدول
            if path == "/create_table":
                t = payload.get("table")
                cols = payload.get("columns", [])
                if not t or not valid_identifier(t):
                    self._send_json({"ok": False, "error": "invalid table"})
                    return

                col_defs = []
                for c in cols:
                    if not valid_identifier(c["name"]):
                        continue
                    col_defs.append(qi(c["name"]) + " " + c["type"])

                sql = f"CREATE TABLE {qi(t)} ({', '.join(col_defs)})"
                conn.execute(sql)
                conn.commit()
                self._send_json({"ok": True})

            # درج رکورد
            elif path.startswith("/insert/"):
                table = path.split("/", 2)[-1]
                s = get_schema(conn, table)
                if not s["ok"]:
                    self._send_json(s)
                    return
                valid_cols = [c["name"] for c in s["columns"] if c["name"] in payload]
                if not valid_cols:
                    self._send_json({"ok": False, "error": "no valid columns"})
                    return
                sql = f"INSERT INTO {qi(table)} ({','.join(qi(c) for c in valid_cols)}) VALUES ({','.join('?' for _ in valid_cols)})"
                conn.execute(sql, [payload[c] for c in valid_cols])
                conn.commit()
                self._send_json({"ok": True})

            # بروزرسانی رکورد
            elif path.startswith("/update/"):
                _, _, table, rowid = path.split("/", 3)
                s = get_schema(conn, table)
                if not s["ok"]:
                    self._send_json(s)
                    return
                # فیلدهای معتبر برای آپدیت
                cols = [c for c in payload.keys() if c in [col["name"] for col in s["columns"]] and c != s["key_field"]]
                if not cols:
                    self._send_json({"ok": False, "error": "no valid fields to update"})
                    return
                set_clause = ", ".join(f'{qi(c)}=?' for c in cols)
                sql = f"UPDATE {qi(table)} SET {set_clause} WHERE {qi(s['key_field'])}=?"
                conn.execute(sql, [payload[c] for c in cols] + [rowid])
                conn.commit()
                self._send_json({"ok": True})

            else:
                self._send_json({"ok": False, "error": "unknown path"}, 404)

        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)
        finally:
            conn.close()

    # دریافت DELETE
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            conn = get_db()
            # حذف رکورد با rowid
            if path.startswith("/delete/"):
                _, _, table, rowid = path.split("/", 3)
                s = get_schema(conn, table)
                if not s["ok"]:
                    self._send_json(s)
                    return
                sql = f"DELETE FROM {qi(table)} WHERE {qi(s['key_field'])}=?"
                conn.execute(sql, (rowid,))
                conn.commit()
                self._send_json({"ok": True})
            else:
                self._send_json({"ok": False, "error": "unknown path"}, 404)
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, 500)
        finally:
            conn.close()

# --------------------- اجرای سرور ---------------------
if __name__ == "__main__":
    httpd = HTTPServer(("", PORT), Handler)
    print(f"Serving at http://localhost:{PORT}")
    httpd.serve_forever()
