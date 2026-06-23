import os
from datetime import datetime, date, timedelta
import pytz
from sqlalchemy.exc import IntegrityError
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    send_from_directory, send_file
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager, login_user, logout_user, login_required,
    current_user, UserMixin
)
import io
import sys
import pandas as pd

# --- Configuración Hora Argentina ---
def now_arg():
    # Ajusta la zona horaria a Buenos Aires
    tz = pytz.timezone('America/Argentina/Buenos_Aires')
    return datetime.now(tz)

def today_arg():
    return now_arg().date()

# --- Config App ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "clave-segura-terminal-123")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///terminal.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# --- Login manager ---
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Debes iniciar sesión."
login_manager.login_message_category = "warning"

# --- Modelos ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="operador")
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=now_arg)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    cuit = db.Column(db.String(20), unique=True, nullable=True)
    telefono = db.Column(db.String(30), nullable=True)
    direccion = db.Column(db.String(200), nullable=True)
    activa = db.Column(db.Boolean, nullable=False, default=True)

class Chofer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    dni = db.Column(db.String(12), unique=True, nullable=False)
    licencia_vencimiento = db.Column(db.Date, nullable=False)
    telefono = db.Column(db.String(30), nullable=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False)
    empresa = db.relationship("Empresa")

class Camion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patente = db.Column(db.String(10), unique=True, nullable=False)
    seguro_vencimiento = db.Column(db.Date, nullable=False)
    marca = db.Column(db.String(50), nullable=True)
    modelo = db.Column(db.String(50), nullable=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False)
    empresa = db.relationship("Empresa")

class Registro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_ingreso = db.Column(db.DateTime, nullable=False, default=now_arg)

    chofer_id = db.Column(db.Integer, db.ForeignKey("chofer.id"), nullable=False)
    camion_id = db.Column(db.Integer, db.ForeignKey("camion.id"), nullable=False)

    precheck_result = db.Column(db.String(20), nullable=False, default="Pendiente")
    precheck_motivo = db.Column(db.String(200), nullable=True)

    inspeccion_neumaticos_ok = db.Column(db.Boolean, nullable=True)
    inspeccion_luces_ok = db.Column(db.Boolean, nullable=True)
    inspeccion_golpes_ok = db.Column(db.Boolean, nullable=True)
    inspeccion_precintos_ok = db.Column(db.Boolean, nullable=True)
    inspeccion_otros_ok = db.Column(db.Boolean, nullable=True)

    inspeccion_result = db.Column(db.String(20), nullable=False, default="Pendiente")
    inspeccion_motivo = db.Column(db.String(200), nullable=True)

    override_forzado = db.Column(db.Boolean, nullable=False, default=False)
    override_motivo = db.Column(db.String(200), nullable=True)
    override_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    observaciones = db.Column(db.Text, nullable=True)

    chofer = db.relationship("Chofer")
    camion = db.relationship("Camion")
    imagenes = db.relationship("Imagen", backref="registro", cascade="all, delete-orphan")

class Imagen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    archivo = db.Column(db.String(200), nullable=False)
    subido_en = db.Column(db.DateTime, nullable=False, default=now_arg)
    registro_id = db.Column(db.Integer, db.ForeignKey("registro.id"), nullable=False)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles:
                flash("No autorizado.", "danger")
                if current_user.role == 'vigilador':
                    return redirect(url_for("precheck"))
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return decorated
    return wrapper

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Rutas de Autenticación ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role in ['vigilador', 'operador']:
            return redirect(url_for("precheck"))
        return redirect(url_for("index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if not user or not user.active or not user.check_password(password):
            flash("Credenciales inválidas.", "danger")
            return redirect(url_for("login"))
        login_user(user, remember=bool(request.form.get("remember")))

        # Redirección según rol
        if user.role in ['vigilador', 'operador']:
            return redirect(url_for("precheck"))
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    if current_user.role == 'vigilador':
        return redirect(url_for("precheck"))

    patente   = (request.args.get("patente") or "").strip().upper()
    dni       = (request.args.get("dni") or "").strip()
    estado    = request.args.get("estado")
    empresa_id= request.args.get("empresa_id")
    desde     = request.args.get("desde")
    hasta     = request.args.get("hasta")

    # Capturamos el número de página (por defecto 1)
    page = request.args.get('page', 1, type=int)

    query = Registro.query.join(Chofer).join(Camion).join(Empresa, Camion.empresa)
    if patente: query = query.filter(Camion.patente.like(f"%{patente}%"))
    if dni:     query = query.filter(Chofer.dni.like(f"%{dni}%"))
    if estado:
        if estado == "Forzado":
            query = query.filter(Registro.override_forzado == True)
        else:
            query = query.filter(Registro.inspeccion_result == estado)
    if empresa_id and empresa_id.isdigit():
        query = query.filter(Camion.empresa_id == int(empresa_id))

    if desde:
        try: query = query.filter(Registro.fecha_ingreso >= datetime.strptime(desde, "%Y-%m-%d"))
        except: pass
    if hasta:
        try: query = query.filter(Registro.fecha_ingreso < (datetime.strptime(hasta, "%Y-%m-%d") + timedelta(days=1)))
        except: pass

    # Aplicamos la paginación (30 por página)
    registros = query.order_by(Registro.fecha_ingreso.desc()).paginate(page=page, per_page=30, error_out=False)

    today = today_arg()
    empresas = Empresa.query.order_by(Empresa.nombre).all()
    return render_template("registros_list.html",
                           registros=registros, patente=patente, dni=dni, estado=estado,
                           empresa_id=empresa_id, empresas=empresas, today=today,
                           desde=desde, hasta=hasta)

# --- Precheck & Inspeccion ---
@app.route("/precheck", methods=["GET", "POST"])
@login_required
def precheck():
    if request.method == "POST":
        dni = (request.form.get("dni") or "").strip()
        patente = (request.form.get("patente") or "").strip().upper()

        if not dni or not patente:
            flash("DNI y Patente son obligatorios.", "warning")
            return redirect(url_for("precheck"))

        chofer = Chofer.query.filter_by(dni=dni).first()
        camion = Camion.query.filter_by(patente=patente).first()
        hoy = today_arg()

        errores = []

        # Analizamos todo al mismo tiempo para reportar todos los fallos
        if not chofer:
            errores.append(f"El chofer DNI {dni} no existe en la base de datos.")
        elif chofer.licencia_vencimiento < hoy:
            errores.append(f"La licencia del chofer está vencida ({chofer.licencia_vencimiento.strftime('%d/%m/%Y')}).")

        if not camion:
            errores.append(f"El camión patente {patente} no existe en la base de datos.")
        elif camion.seguro_vencimiento < hoy:
            errores.append(f"El seguro del camión está vencido ({camion.seguro_vencimiento.strftime('%d/%m/%Y')}).")

        # Si falta el chofer o el camión de la base de datos, bloqueamos acá y mostramos TODOS los errores
        if not chofer or not camion:
            return render_template("precheck_result.html", puede=False, motivos=errores, registro=None, modo_vigilador=(current_user.role == 'vigilador'))

        # Si ambos existen, registramos en el historial
        motivos_rechazo = []
        vencidos_cortos = []
        if chofer.licencia_vencimiento < hoy:
            motivos_rechazo.append(f"Licencia vencida ({chofer.licencia_vencimiento.strftime('%d/%m/%Y')})")
            vencidos_cortos.append("Lic")
        if camion.seguro_vencimiento < hoy:
            motivos_rechazo.append(f"Seguro vencido ({camion.seguro_vencimiento.strftime('%d/%m/%Y')})")
            vencidos_cortos.append("Seg")

        nuevo_reg = Registro(chofer_id=chofer.id, camion_id=camion.id)

        if motivos_rechazo:
            if len(vencidos_cortos) == 2:
                nuevo_reg.precheck_result = "Actualizar Lic/Seg"
            else:
                nuevo_reg.precheck_result = f"Actualizar {vencidos_cortos[0]}"
            nuevo_reg.precheck_motivo = ", ".join(motivos_rechazo)
        else:
            nuevo_reg.precheck_result = "Aprobado"

        db.session.add(nuevo_reg)
        db.session.commit()

        es_vigilador = (current_user.role == 'vigilador')
        return render_template("precheck_result.html",
                               puede=(nuevo_reg.precheck_result == "Aprobado"),
                               motivos=motivos_rechazo,
                               registro=nuevo_reg,
                               modo_vigilador=es_vigilador)

    return render_template("precheck_form.html")

@app.route("/inspeccion/<int:registro_id>", methods=["GET", "POST"])
@login_required
def inspeccion(registro_id):
    reg = Registro.query.get_or_404(registro_id)
    if request.method == "POST":
        neum = request.form.get("neumaticos") == "ok"
        luces = request.form.get("luces") == "ok"
        golpes = request.form.get("golpes") == "ok"
        precintos = request.form.get("precintos") == "ok"
        otros = request.form.get("otros") == "ok"

        reg.inspeccion_neumaticos_ok = neum
        reg.inspeccion_luces_ok = luces
        reg.inspeccion_golpes_ok = golpes
        reg.inspeccion_precintos_ok = precintos
        reg.inspeccion_otros_ok = otros

        reg.observaciones = request.form.get("observaciones")

        files = request.files.getlist("imagenes")
        for f in files:
            if f and allowed_file(f.filename):
                fname = secure_filename(f.filename)
                stamp = datetime.now().strftime("%Y%m%d%H%M%S")
                sname = f"{reg.id}_{stamp}.{fname.rsplit('.',1)[1]}"
                f.save(os.path.join(app.config["UPLOAD_FOLDER"], sname))
                db.session.add(Imagen(archivo=sname, registro_id=reg.id))

        if all([neum, luces, golpes, precintos, otros]):
            reg.inspeccion_result = "Aprobado"
        else:
            reg.inspeccion_result = "Rechazado"
            reg.inspeccion_motivo = "Falla inspección visual"

        db.session.commit()
        if current_user.role == 'vigilador': return redirect(url_for("precheck"))
        return redirect(url_for("registro_detalle", registro_id=reg.id))

    return render_template("inspeccion_form.html", reg=reg)

# --- CRUDs ADMINISTRATIVOS ---

# --- CRUDs ADMINISTRATIVOS ---

# EMPRESAS
@app.route("/admin/empresas")
@login_required
@role_required("admin", "operador")
def empresas_list():
    q = request.args.get("q", "").strip()
    page = request.args.get('page', 1, type=int)

    query = Empresa.query
    if q: query = query.filter(Empresa.nombre.ilike(f"%{q}%"))

    empresas = query.order_by(Empresa.nombre).paginate(page=page, per_page=30, error_out=False)
    return render_template("empresas_list.html", empresas=empresas, q=q)

@app.route("/admin/empresas/nueva", methods=["GET", "POST"])
@login_required
@role_required("admin", "operador")
def empresa_nueva():
    if request.method == "POST":
        nombre_nuevo = request.form.get("nombre").strip().upper()
        cuit_val = request.form.get("cuit")

        # Convertimos el texto vacío en None para evitar el error de "UNIQUE constraint"
        cuit_val = cuit_val.strip() if cuit_val and cuit_val.strip() != "" else None

        # Validación de duplicados
        if Empresa.query.filter(Empresa.nombre.ilike(nombre_nuevo)).first():
            flash(f"Error: La empresa '{nombre_nuevo}' ya existe.", "danger")
            return render_template("empresa_form.html", empresa=None)

        if cuit_val and Empresa.query.filter_by(cuit=cuit_val).first():
            flash(f"Error: El CUIT {cuit_val} ya está registrado en otra empresa.", "danger")
            return render_template("empresa_form.html", empresa=None)

        e = Empresa(
            nombre=nombre_nuevo,
            cuit=cuit_val,
            telefono=request.form.get("telefono"),
            direccion=request.form.get("direccion"),
            activa=bool(request.form.get("activa"))
        )
        db.session.add(e)
        db.session.commit()
        flash("Empresa creada exitosamente.", "success")
        return redirect(url_for("empresas_list"))
    return render_template("empresa_form.html", empresa=None)

@app.route("/admin/empresas/<int:id>/editar", methods=["GET", "POST"])
@login_required
@role_required("admin", "operador")
def empresa_editar(id):
    e = Empresa.query.get_or_404(id)
    if request.method == "POST":
        nombre_nuevo = request.form.get("nombre").strip().upper()
        cuit_val = request.form.get("cuit")
        cuit_val = cuit_val.strip() if cuit_val and cuit_val.strip() != "" else None

        # Validación de duplicados (ignorando la empresa actual que estamos editando)
        if Empresa.query.filter(Empresa.nombre.ilike(nombre_nuevo), Empresa.id != id).first():
            flash(f"Error: La empresa '{nombre_nuevo}' ya existe.", "danger")
            return render_template("empresa_form.html", empresa=e)

        if cuit_val and Empresa.query.filter(Empresa.cuit == cuit_val, Empresa.id != id).first():
            flash(f"Error: El CUIT {cuit_val} ya está registrado en otra empresa.", "danger")
            return render_template("empresa_form.html", empresa=e)

        e.nombre    = nombre_nuevo
        e.cuit      = cuit_val
        e.telefono  = request.form.get("telefono")
        e.direccion = request.form.get("direccion")
        e.activa    = bool(request.form.get("activa"))
        db.session.commit()
        flash("Empresa actualizada exitosamente.", "success")
        return redirect(url_for("empresas_list"))
    return render_template("empresa_form.html", empresa=e)

# CHOFERES
@app.route("/admin/choferes")
@login_required
@role_required("admin", "operador")
def choferes_list():
    q = request.args.get("q", "").strip()
    page = request.args.get('page', 1, type=int)

    query = Chofer.query
    if q: query = query.filter(Chofer.dni.ilike(f"%{q}%"))

    choferes = query.order_by(Chofer.nombre).paginate(page=page, per_page=30, error_out=False)
    return render_template("choferes_list.html", choferes=choferes, today=today_arg(), q=q)

@app.route("/admin/choferes/nuevo", methods=["GET", "POST"])
@login_required
@role_required("admin", "operador")
def chofer_nuevo():
    empresas = Empresa.query.filter_by(activa=True).order_by(Empresa.nombre).all()
    if request.method == "POST":
        dni_nuevo = request.form.get("dni").strip()

        # Validación de duplicados
        if Chofer.query.filter_by(dni=dni_nuevo).first():
            flash(f"Error: El DNI {dni_nuevo} ya se encuentra registrado.", "danger")
            return render_template("chofer_form.html", chofer=None, empresas=empresas)

        c = Chofer(
            nombre=request.form.get("nombre").strip().upper(),
            dni=dni_nuevo,
            licencia_vencimiento=datetime.strptime(request.form.get("licencia_vencimiento"), "%Y-%m-%d"),
            telefono=request.form.get("telefono"),
            empresa_id=request.form.get("empresa_id")
        )
        db.session.add(c)
        db.session.commit()
        flash("Chofer creado exitosamente.", "success")
        return redirect(url_for("choferes_list"))
    return render_template("chofer_form.html", chofer=None, empresas=empresas)

@app.route("/admin/choferes/<int:chofer_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("admin", "operador")
def chofer_editar(chofer_id):
    c = Chofer.query.get_or_404(chofer_id)
    empresas = Empresa.query.filter_by(activa=True).order_by(Empresa.nombre).all()
    if request.method == "POST":
        dni_nuevo = request.form.get("dni").strip()

        # Validación de duplicados (ignorando el chofer actual)
        if Chofer.query.filter(Chofer.dni == dni_nuevo, Chofer.id != chofer_id).first():
            flash(f"Error: El DNI {dni_nuevo} pertenece a otro chofer.", "danger")
            return render_template("chofer_form.html", chofer=c, empresas=empresas)

        c.nombre = request.form.get("nombre").strip().upper()
        c.dni = dni_nuevo
        c.licencia_vencimiento = datetime.strptime(request.form.get("licencia_vencimiento"), "%Y-%m-%d")
        c.telefono = request.form.get("telefono")
        c.empresa_id = request.form.get("empresa_id")
        db.session.commit()
        flash("Chofer actualizado exitosamente.", "success")
        return redirect(url_for("choferes_list"))
    return render_template("chofer_form.html", chofer=c, empresas=empresas)

# CAMIONES
@app.route("/admin/camiones")
@login_required
@role_required("admin", "operador")
def camiones_list():
    q = request.args.get("q", "").strip()
    page = request.args.get('page', 1, type=int)

    query = Camion.query
    if q: query = query.filter(Camion.patente.ilike(f"%{q}%"))

    camiones = query.order_by(Camion.patente).paginate(page=page, per_page=30, error_out=False)
    return render_template("camiones_list.html", camiones=camiones, today=today_arg(), q=q)

@app.route("/admin/camiones/nuevo", methods=["GET", "POST"])
@login_required
@role_required("admin", "operador")
def camion_nuevo():
    empresas = Empresa.query.filter_by(activa=True).order_by(Empresa.nombre).all()
    if request.method == "POST":
        patente_nueva = request.form.get("patente").strip().upper()

        # Validación de duplicados
        if Camion.query.filter_by(patente=patente_nueva).first():
            flash(f"Error: La patente {patente_nueva} ya existe en el sistema.", "danger")
            return render_template("camion_form.html", camion=None, empresas=empresas)

        c = Camion(
            patente=patente_nueva,
            seguro_vencimiento=datetime.strptime(request.form.get("seguro_vencimiento"), "%Y-%m-%d"),
            marca=request.form.get("marca"),
            modelo=request.form.get("modelo"),
            empresa_id=request.form.get("empresa_id")
        )
        db.session.add(c)
        db.session.commit()
        flash("Camión creado exitosamente.", "success")
        return redirect(url_for("camiones_list"))

    return render_template("camion_form.html", camion=None, empresas=empresas)

@app.route("/admin/camiones/<int:camion_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("admin", "operador")
def camion_editar(camion_id):
    c = Camion.query.get_or_404(camion_id)
    empresas = Empresa.query.filter_by(activa=True).order_by(Empresa.nombre).all()
    if request.method == "POST":
        patente_nueva = request.form.get("patente").strip().upper()

        # Validación de duplicados (ignorando el camión actual)
        if Camion.query.filter(Camion.patente == patente_nueva, Camion.id != camion_id).first():
            flash(f"Error: La patente {patente_nueva} ya pertenece a otro camión.", "danger")
            return render_template("camion_form.html", camion=c, empresas=empresas)

        c.patente = patente_nueva
        c.seguro_vencimiento = datetime.strptime(request.form.get("seguro_vencimiento"), "%Y-%m-%d")
        c.marca = request.form.get("marca")
        c.modelo = request.form.get("modelo")
        c.empresa_id = request.form.get("empresa_id")
        db.session.commit()
        flash("Camión actualizado exitosamente.", "success")
        return redirect(url_for("camiones_list"))
    return render_template("camion_form.html", camion=c, empresas=empresas)

# USUARIOS
@app.route("/admin/usuarios")
@login_required
@role_required("admin")
def usuarios_list():
    usuarios = User.query.all()
    return render_template("users_list.html", usuarios=usuarios)

@app.route("/admin/usuarios/nuevo", methods=["GET", "POST"])
@login_required
@role_required("admin")
def usuario_nuevo():
    if request.method == "POST":
        u = User(
            username=request.form.get("username"),
            nombre=request.form.get("nombre"),
            role=request.form.get("role"),
            active=bool(request.form.get("active"))
        )
        u.set_password(request.form.get("password"))
        db.session.add(u)
        db.session.commit()
        return redirect(url_for("usuarios_list"))
    return render_template("user_form.html", usuario=None)

@app.route("/admin/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("admin")
def usuario_editar(user_id):
    u = User.query.get_or_404(user_id)
    if request.method == "POST":
        u.nombre = request.form.get("nombre")
        u.role = request.form.get("role")
        u.active = bool(request.form.get("active"))
        if request.form.get("password"):
            u.set_password(request.form.get("password"))
        db.session.commit()
        return redirect(url_for("usuarios_list"))
    return render_template("user_form.html", usuario=u)

@app.route("/admin/usuarios/<int:user_id>/eliminar", methods=["POST"])
@login_required
@role_required("admin")
def usuario_eliminar(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("No puedes eliminar tu propio usuario mientras estás conectado.", "danger")
        return redirect(url_for("usuarios_list"))

    db.session.delete(u)
    db.session.commit()
    flash(f"Usuario {u.username} eliminado permanentemente.", "success")
    return redirect(url_for("usuarios_list"))

# --- Otros ---
@app.route("/registro/<int:registro_id>")
@login_required
def registro_detalle(registro_id):
    reg = Registro.query.get_or_404(registro_id)
    hoy = today_arg()
    return render_template("registro_detail.html", reg=reg, licencia_vencida=(reg.chofer.licencia_vencimiento<hoy), seguro_vencido=(reg.camion.seguro_vencimiento<hoy))

@app.route("/registro/<int:registro_id>/eliminar", methods=["POST"])
@login_required
@role_required("admin")
def registro_eliminar(registro_id):
    db.session.delete(Registro.query.get_or_404(registro_id))
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/forzar/<int:registro_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def forzar(registro_id):
    reg = Registro.query.get_or_404(registro_id)
    if request.method == "POST":
        motivo = request.form.get("motivo")
        if not motivo:
            flash("Motivo requerido", "warning")
            return redirect(url_for("forzar", registro_id=reg.id))

        reg.override_forzado = True
        reg.override_motivo = motivo
        reg.override_by_user_id = current_user.id
        db.session.commit()
        flash("Ingreso forzado.", "success")
        return redirect(url_for("registro_detalle", registro_id=reg.id))
    return render_template("forzar_form.html", reg=reg)

@app.route("/uploads/<path:filename>")
@login_required
def uploads(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/exportar.xlsx")
@login_required
@role_required("admin")
def exportar_xlsx():
    patente = (request.args.get("patente") or "").strip().upper()
    dni = (request.args.get("dni") or "").strip()
    estado = request.args.get("estado")
    empresa_id = request.args.get("empresa_id")
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")

    query = Registro.query.join(Chofer).join(Camion).join(Empresa, Camion.empresa)
    if patente: query = query.filter(Camion.patente.like(f"%{patente}%"))
    if dni: query = query.filter(Chofer.dni.like(f"%{dni}%"))
    if estado:
        if estado == "Forzado": query = query.filter(Registro.override_forzado == True)
        else: query = query.filter(Registro.inspeccion_result == estado)
    if empresa_id and empresa_id.isdigit():
        query = query.filter(Camion.empresa_id == int(empresa_id))
    if desde:
        try: query = query.filter(Registro.fecha_ingreso >= datetime.strptime(desde, "%Y-%m-%d"))
        except: pass
    if hasta:
        try: query = query.filter(Registro.fecha_ingreso < (datetime.strptime(hasta, "%Y-%m-%d") + timedelta(days=1)))
        except: pass

    registros = query.order_by(Registro.fecha_ingreso.desc()).all()

    data = []
    for r in registros:
        motivo_real = ""
        if r.override_forzado:
            motivo_real = f"FORZADO: {r.override_motivo}"
        elif r.inspeccion_motivo:
            motivo_real = r.inspeccion_motivo
        elif r.precheck_motivo:
            motivo_real = r.precheck_motivo

        data.append({
            "ID": r.id,
            "Fecha": r.fecha_ingreso.strftime("%d/%m/%Y %H:%M"),
            "Patente": r.camion.patente,
            "Chofer": r.chofer.nombre,
            "DNI": r.chofer.dni,
            "Empresa Tpte": r.camion.empresa.nombre,
            "Precheck": r.precheck_result,
            "Inspección": "Forzado" if r.override_forzado else r.inspeccion_result,
            "Motivo / Observación": motivo_real,
            "Fotos": len(r.imagenes)
        })

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Ingresos')
        for column in df:
            column_width = max(df[column].astype(str).map(len).max(), len(column))
            col_idx = df.columns.get_loc(column)
            writer.sheets['Ingresos'].column_dimensions[chr(65 + col_idx)].width = column_width + 2

    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'Reporte_Ingresos_{today_arg()}.xlsx'
    )

# --- CLI Creator ---
def create_admin_cli():
    with app.app_context():
        if not User.query.filter_by(username="admin").first():
            u = User(username="admin", nombre="Administrador", role="admin")
            u.set_password("admin123")
            db.session.add(u)
            db.session.commit()
            print("Admin creado (user: admin, pass: admin123)")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "create-admin": create_admin_cli()
    else: app.run(debug=True)