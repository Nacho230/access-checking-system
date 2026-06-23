from app import app, db, User

# Entramos al contexto de la aplicación para poder usar la base de datos
with app.app_context():
    # Aseguramos que las tablas existan
    db.create_all()
    
    print("--- Intentando crear usuario administrador ---")
    
    # Verificamos si ya existe para no duplicar
    if User.query.filter_by(username="admin").first():
        print("⚠️ El usuario 'admin' YA EXISTE en la base de datos.")
        print("No se realizaron cambios.")
    else:
        # Creamos el usuario manualmente
        # IMPORTANTE: Aquí definimos la contraseña fija 'admin123'
        u = User(username="admin", nombre="Administrador", role="admin", active=True)
        u.set_password("admin123") 
        
        db.session.add(u)
        db.session.commit()
        
        print("✅ ¡Éxito! Usuario creado.")
        print("Usuario: admin")
        print("Contraseña: admin123")