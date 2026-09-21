# 🚛 Access Checking - Sistema de Control de Accesos Logísticos

[![Python](https://img.shields.io/badge/Python-3.x-blue?style=flat-square&logo=python)]()
[![Flask](https://img.shields.io/badge/Flask-Backend-black?style=flat-square&logo=flask)]()
[![SQLite](https://img.shields.io/badge/SQLite-Database-lightgrey?style=flat-square&logo=sqlite)]()
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple?style=flat-square&logo=bootstrap)]()
[![Pandas](https://img.shields.io/badge/Pandas-Data_Processing-darkblue?style=flat-square&logo=pandas)]()

Un sistema integral web (Full-Stack) diseñado para gestionar, auditar y agilizar el control de accesos de flotas logísticas (choferes y camiones) en terminales o plantas industriales.

El proyecto reemplaza el seguimiento manual por una plataforma automatizada que valida documentación en tiempo real, previene el ingreso de unidades no autorizadas y mantiene un registro histórico detallado.

**Nota sobre el proceso de desarrollo:** este proyecto fue construido con desarrollo asistido por IA (Gemini), como parte de mi flujo de trabajo real trabajando con herramientas de IA generativa. Definí los requerimientos y la lógica de negocio, y mi trabajo se centró en la revisión funcional del código generado: debugging, corrección de partes que no funcionaban, verificación de datos e implementaciones, y despliegue en producción (PythonAnywhere). Entiendo en profundidad cómo funciona cada módulo del sistema y puedo explicar y justificar las decisiones técnicas detrás de él.

---

## 🚀 Características Principales

**Sistema de Roles y Permisos**

- Administrador: acceso total (Dashboard, auditoría, ABM de usuarios y flotas).
- Operador: gestión de "materia prima" (ABM de Empresas, Choferes y Camiones).
- Vigilador: operativa en puerta (solo visualiza el módulo de Nuevo Ingreso y carga inspecciones).

**Motor de "Precheck" Inteligente**

Validación automática de vencimientos de licencias de conducir y seguros vehiculares al momento de solicitar el ingreso.

**Inspección Física**

Registro detallado del estado de la unidad (neumáticos, luces, precintos) con posibilidad de adjuntar evidencia fotográfica.

**Tablero de Control (Dashboard)**

Vista gerencial con filtros combinados (fecha, DNI, patente, empresa, estado) y reportes en tiempo real.

**Importación Masiva (Data Wrangling)**

Script automatizado para la ingesta de bases de datos desde Excel/CSV, con limpieza de datos en caliente (manejo de nulos, corrección de tipos de datos de Excel y prevención de duplicados).

**Exportación de Reportes**

Generación de planillas Excel (.xlsx) al vuelo para auditorías.

---

## 🛠️ Stack Tecnológico

**Backend**

- Python 3
- Flask y Flask-Login (autenticación y ruteo)
- SQLAlchemy (ORM)

**Frontend**

- HTML5 y CSS3
- Jinja2 (motor de plantillas)
- Bootstrap 5 (UI/UX responsivo)

**Base de Datos y Procesamiento**

- SQLite
- Pandas y OpenPyXL (manejo de archivos Excel/CSV)
- Pytz (control estricto de zonas horarias)

El stack se definió considerando las limitaciones del entorno de despliegue (PythonAnywhere) y con apoyo de IA para evaluar alternativas.

---

## 🧠 Desafíos Técnicos Resueltos

Durante el desarrollo y depuración de este proyecto, trabajé sobre retos propios de un entorno de producción real, entendiendo y validando en profundidad:

**Integridad de Datos**

Lógicas para atrapar errores IntegrityError en la base de datos, previniendo patentes y DNIs duplicados mediante validaciones previas en los controladores.

**Limpieza de Datos de Excel**

Algoritmos con Pandas para procesar archivos de origen imperfectos (por ejemplo, transformar números de DNI leídos como floats 12345678.0 a strings limpios, y estandarizar fechas vacías o con formatos incorrectos).

**Optimización de Consultas**

Paginación en las vistas de listas y el dashboard mediante SQLAlchemy, reduciendo drásticamente el tiempo de carga del servidor y mejorando la experiencia del usuario al manejar grandes volúmenes de registros.

Cada uno de estos puntos fue revisado, corregido y verificado por mí hasta confirmar su correcto funcionamiento en producción.
