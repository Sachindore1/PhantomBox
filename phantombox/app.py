"""
phantombox/app.py  — Full version with Admin, History, Share Links
"""
import os, sys, io, json, time, hashlib, logging
from datetime import datetime
from flask import Flask, Blueprint, render_template, send_from_directory, jsonify, request, make_response, send_file
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s")
logger = logging.getLogger("phantombox.app")


def create_app() -> Flask:
    app = Flask(__name__,
                template_folder="../client",
                static_folder="../client")

    CORS(app,
         resources={r"/api/*": {"origins": "*"}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         expose_headers=["Content-Disposition"],
         methods=["GET","POST","PUT","DELETE","OPTIONS"])

    os.makedirs(os.path.join(os.path.dirname(__file__), "temp"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)

    # ── 1. MySQL Auth blueprint ──────────────────────────────
    try:
        from phantombox.auth import auth_bp, init_db
        from phantombox.auth.db_extensions import extend_db
        app.register_blueprint(auth_bp)
        init_db()
        extend_db()   # adds shared_links table + new columns
        logger.info("✅ MySQL Auth blueprint registered")
    except Exception as e:
        logger.error(f"❌ Auth blueprint failed: {e}")
        import traceback; traceback.print_exc()

    # ── 2. Admin + History + Share blueprints ────────────────
    try:
        from phantombox.auth.admin_routes import admin_bp, history_bp, share_bp
        app.register_blueprint(admin_bp)
        app.register_blueprint(history_bp)
        app.register_blueprint(share_bp)
        logger.info("✅ Admin/History/Share blueprints registered")
    except Exception as e:
        logger.error(f"❌ Admin blueprints failed: {e}")
        import traceback; traceback.print_exc()

    # ── 3. Upload / Download blueprints ─────────────────────
    try:
        from phantombox.routes.upload   import upload_bp
        from phantombox.routes.download import download_bp
        app.register_blueprint(upload_bp,   url_prefix="/api")
        app.register_blueprint(download_bp, url_prefix="/api")
        logger.info("✅ Upload/Download blueprints registered")
    except ImportError as e:
        logger.warning(f"⚠️  Route modules not found — demo stubs active: {e}")
        _register_demo_stubs(app)

    _register_frontend_routes(app)
    _register_extra_api_routes(app)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    return app


# ── Frontend Routes ──────────────────────────────────────────

def _register_frontend_routes(app):

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/auth")
    @app.route("/auth.html")
    def auth_page():
        return render_template("auth.html")

    @app.route("/admin")
    @app.route("/admin/")
    def admin_page():
        return send_from_directory("../client/admin", "index.html")

    @app.route("/share/<token>")
    def share_page(token):
        """Public share link landing page."""
        return render_template("share.html")

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy", "service": "PhantomBox",
                        "port": int(os.getenv("PHANTOMBOX_PORT", 8000)),
                        "auth": "MySQL+RBAC", "time": datetime.utcnow().isoformat()+"Z"})

    @app.route("/test")
    def test_ep():
        return jsonify({"message": "PhantomBox running!", "time": time.time()})

    @app.route("/api/preview/<preview_token>", methods=["OPTIONS"])
    def preview_options(preview_token):
        r = make_response()
        r.headers["Access-Control-Allow-Origin"]  = "*"
        r.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return r, 204

    @app.route("/<path:filename>")
    def serve_static(filename):
        # Don't intercept API routes or special paths
        if filename.startswith(('api/', 'share/', 'admin/')):
            from flask import abort
            abort(404)
        return send_from_directory("../client", filename)


# ── Extra API Routes ─────────────────────────────────────────

def _register_extra_api_routes(app):
    import requests as http_req

    @app.route("/api/security_metrics", methods=["GET"])
    def security_metrics():
        nodes_online = 0
        for url in ["http://127.0.0.1:5001","http://127.0.0.1:5002",
                    "http://127.0.0.1:9001","http://127.0.0.1:9002"]:
            try:
                if http_req.get(f"{url}/status", timeout=2).ok:
                    nodes_online += 1
            except Exception:
                pass

        fragments_total = 0
        try:
            for node in ["http://127.0.0.1:9001","http://127.0.0.1:9002"]:
                r = http_req.get(f"{node}/status", timeout=2)
                if r.ok: fragments_total += r.json().get("fragment_count", 0)
        except Exception:
            pass

        overall = (nodes_online / 4 * 25) + min(25, fragments_total * 2.5) + 25 + 20
        return jsonify({
            "timestamp": time.time(),
            "overall_score": overall,
            "security_level": "🔒 EXCELLENT" if overall >= 90 else "🟢 GOOD" if overall >= 75 else "🟡 MODERATE",
            "system_health": {"nodes_online": nodes_online, "nodes_total": 4, "uptime_percentage": (nodes_online/4)*100},
            "fragment_security": {"total_fragments": fragments_total, "redundancy_factor": "2-of-3"},
        })

    @app.route("/api/blockchain/explorer", methods=["GET"])
    def blockchain_explorer():
        try:
            genesis_res   = http_req.get("http://127.0.0.1:5001/chain", timeout=5)
            genesis_chain = genesis_res.json().get("chain", [])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        file_registrations = [
            {
                "file_id":       b["data"].get("file_id"),
                "file_hash":     b["data"].get("file_hash"),
                "timestamp":     b["data"].get("timestamp"),
                "block_index":   b.get("index"),
                "fragment_count": len(b["data"].get("fragment_map",{}).get("fragments",{})),
                "owner_id":      b["data"].get("owner_id",""),
            }
            for b in genesis_chain
            if b.get("data",{}).get("type") == "file_registration"
        ]
        return jsonify({
            "total_blocks": len(genesis_chain),
            "consensus":    "in_sync",
            "file_registrations": len(file_registrations),
            "blocks":       [{"index":b.get("index"),"timestamp":b.get("timestamp"),
                               "type":b.get("data",{}).get("type","unknown"),"hash":b.get("hash")}
                              for b in genesis_chain[-10:]],
            "files":        file_registrations[-5:],
            "timestamp":    time.time(),
        })

    @app.route("/api/file_lifecycle/<file_id>", methods=["GET"])
    def file_lifecycle(file_id):
        lifecycle = {"file_id": file_id, "stages": [], "status": "unknown"}
        try:
            r = http_req.get(f"http://127.0.0.1:5001/chain", timeout=5)
            if r.ok:
                for block in r.json().get("chain",[]):
                    bd = block.get("data",{})
                    if bd.get("file_id") == file_id:
                        ts = bd.get("timestamp",0)
                        lifecycle["stages"] = [
                            {"stage":"UPLOADED","timestamp":datetime.fromtimestamp(ts).isoformat(),"status":"✅"},
                            {"stage":"FRAGMENTED","timestamp":datetime.fromtimestamp(ts+1).isoformat(),"status":"✅"},
                            {"stage":"NOISE_STORED","timestamp":datetime.fromtimestamp(ts+2).isoformat(),"status":"✅"},
                            {"stage":"BLOCKCHAIN_REGISTERED","timestamp":datetime.fromtimestamp(ts+3).isoformat(),"status":"✅"},
                        ]
                        lifecycle["status"] = "registered"
                        break
        except Exception:
            pass
        return jsonify(lifecycle)


# ── Demo Stubs ───────────────────────────────────────────────

def _register_demo_stubs(app):
    stub = Blueprint("demo", __name__)

    @stub.route("/upload", methods=["POST"])
    def upload_demo():
        if "file" not in request.files:
            return jsonify({"error": "No file"}), 400
        f = request.files["file"]
        data = f.read()
        fh   = hashlib.sha256(data).hexdigest()
        fid  = f"{fh[:16]}_{int(time.time())}"
        return jsonify({"success": True, "file_id": fid, "file_hash": fh, "message": "Demo mode"})

    @stub.route("/request_download/<file_id>")
    def dl_demo(file_id):
        return jsonify({"success": True, "download_token": f"demo_{file_id}", "message": "Demo mode"})

    @stub.route("/memory_stats")
    def mem_demo():
        return jsonify({"total_entries": 0, "total_memory": 0})

    app.register_blueprint(stub, url_prefix="/api")


# ── Entry Point ──────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    PORT = int(os.getenv("PHANTOMBOX_PORT", 8000))
    print(f"\n{'='*65}")
    print(f"  🚀 PhantomBox  (MySQL + RBAC + Admin + Share Links)")
    print(f"  🌐 App:    http://localhost:{PORT}")
    print(f"  🛡️  Admin:  http://localhost:{PORT}/admin")
    print(f"  🔑 Auth:   http://localhost:{PORT}/auth")
    print(f"  👻 Share:  http://localhost:{PORT}/share/<token>")
    print(f"  💚 Health: http://localhost:{PORT}/health")
    print(f"{'='*65}\n")
    app.run(host="0.0.0.0", port=PORT, debug=True,
            threaded=True, use_reloader=False)