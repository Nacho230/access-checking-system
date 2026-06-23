import pandas as pd
from datetime import datetime
from app import app, db, Chofer, Camion, Empresa

# --- CONFIGURACIÓN ---
NOMBRE_ARCHIVO = "CHOFERES Y CAMIONES.xlsx"

# Nombres de las pestañas en tu Excel
HOJA_CHOFERES = "CHOFERES" 
HOJA_CAMIONES = "CAMIONES" 

# ==========================================
# 🛠️ HERRAMIENTAS DE LIMPIEZA
# ==========================================

def limpiar_dni(valor):
    """
    Transforma 123456.0 -> "123456"
    Quita el decimal que agrega Excel a veces.
    """
    try:
        s = str(valor).strip()
        if s.endswith('.0'):
            return s[:-2] # Corta los ultimos 2 caracteres (.0)
        return s
    except:
        return str(valor).strip()

def limpiar_fecha(fecha):
    """Maneja fechas vacías, guiones o errores."""
    try:
        s = str(fecha).strip()
        if not s or s in ["—", "-", "nan", "NaT"]:
            return datetime(2030, 1, 1).date()
        return pd.to_datetime(fecha).date()
    except:
        return datetime(2030, 1, 1).date()

def get_empresa(nombre):
    """Busca o crea la empresa."""
    if pd.isna(nombre) or str(nombre).strip() == "":
        nombre_clean = "EMPRESA GENERICA"
    else:
        nombre_clean = str(nombre).strip().upper()
    
    emp = Empresa.query.filter_by(nombre=nombre_clean).first()
    if not emp:
        emp = Empresa(nombre=nombre_clean, activa=True)
        db.session.add(emp)
        db.session.commit()
    return emp

# ==========================================
# 🚀 PROCESO DE IMPORTACIÓN
# ==========================================

def importar_todo():
    print(f"🚀 LEYENDO ARCHIVO MAESTRO: {NOMBRE_ARCHIVO}...")
    
    # --- 1. PROCESAR CHOFERES ---
    print(f"\n--- CARGANDO HOJA: {HOJA_CHOFERES} ---")
    try:
        # Leemos la pestaña específica del Excel
        df = pd.read_excel(NOMBRE_ARCHIVO, sheet_name=HOJA_CHOFERES)
        
        count = 0
        nuevos = 0
        for _, row in df.iterrows():
            # Limpiamos el DNI aquí
            dni = limpiar_dni(row.get("DNI"))
            nombre = str(row.get("CHOFER", "")).strip().upper()
            empresa_nom = row.get("EMPRESA", "")
            vencimiento = row.get("VENCIMIENTO REGISTRO")

            if len(dni) < 5: continue
            
            # Verificamos si existe
            if Chofer.query.filter_by(dni=dni).first(): continue

            emp = get_empresa(empresa_nom)
            
            nuevo = Chofer(
                nombre=nombre,
                dni=dni,
                licencia_vencimiento=limpiar_fecha(vencimiento),
                telefono="No informado",
                empresa_id=emp.id
            )
            db.session.add(nuevo)
            nuevos += 1
            count += 1
            
        db.session.commit()
        print(f"✅ {nuevos} Choferes importados (DNIs corregidos).")
            
    except Exception as e:
        print(f"❌ Error leyendo la hoja de Choferes: {e}")
        print("   (Verifica que la pestaña del Excel se llame exactamente 'CHOFERES')")

    # --- 2. PROCESAR CAMIONES ---
    print(f"\n--- CARGANDO HOJA: {HOJA_CAMIONES} ---")
    try:
        # Leemos la pestaña específica del Excel
        df = pd.read_excel(NOMBRE_ARCHIVO, sheet_name=HOJA_CAMIONES)
        
        count = 0
        nuevos = 0
        for _, row in df.iterrows():
            patente = str(row.get("PATENTE", "")).strip().upper()
            empresa_nom = row.get("EMPRESA", "")
            vencimiento = row.get("VENC SEGURO") 

            if len(patente) < 3: continue
            
            if Camion.query.filter_by(patente=patente).first(): continue

            emp = get_empresa(empresa_nom)

            nuevo = Camion(
                patente=patente,
                seguro_vencimiento=limpiar_fecha(vencimiento),
                marca="DESCONOCIDA",
                modelo="GENERICO",
                empresa_id=emp.id
            )
            db.session.add(nuevo)
            nuevos += 1
            count += 1
            
        db.session.commit()
        print(f"✅ {nuevos} Camiones importados.")

    except Exception as e:
        print(f"❌ Error leyendo la hoja de Camiones: {e}")
        print("   (Verifica que la pestaña del Excel se llame exactamente 'CAMIONES')")

if __name__ == "__main__":
    with app.app_context():
        importar_todo()
        print("\n🏁 FINALIZADO.")