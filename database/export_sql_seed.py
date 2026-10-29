"""Export the current MySQL database as SQL INSERT statements for seed/replay."""
import json
from pathlib import Path
from database.connection import get_connection

ROOT = Path(__file__).resolve().parents[1]
TABLES = ["products","promotions","cost_records","promotion_rules","price_history","competitor_observations","inventory_snapshots","orders","price_decisions","promotion_products","promotion_applications","audit_events"]

def quote(value):
    if value is None: return "NULL"
    if isinstance(value, bool): return "1" if value else "0"
    if isinstance(value, (int,float)): return str(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\x00", "") + "'"

def export():
    conn=get_connection(); out=ROOT/"database"/"database_dump.sql"; count=0
    try:
        with out.open("w",encoding="utf-8",newline="\n") as f:
            f.write("-- Generated from the current pricing_intelligence MySQL database.\nSET FOREIGN_KEY_CHECKS=0;\n")
            for table in TABLES:
                cur=conn.cursor(dictionary=True); cur.execute(f"SELECT * FROM `{table}`")
                columns=[d[0] for d in cur.description]
                f.write(f"\n-- Table: {table}\n")
                while True:
                    rows=cur.fetchmany(1000)
                    if not rows: break
                    for row in rows:
                        col_sql=", ".join(f"`{c}`" for c in columns)
                        values=", ".join(quote(row[c]) for c in columns)
                        f.write(f"INSERT INTO `{table}` ({col_sql}) VALUES ({values});\n")
                        count+=1
                cur.close()
            f.write("\nSET FOREIGN_KEY_CHECKS=1;\n")
    finally: conn.close()
    return {"file":str(out),"rows_exported":count}

if __name__=="__main__": print(json.dumps(export(),indent=2))
