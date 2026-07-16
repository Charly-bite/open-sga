# Sistema de Gestión de Usuarios - SGA

## 📋 Descripción General

El Sistema de Gestión de Almacén (SGA) ahora incluye un sistema completo de autenticación y control de usuarios. Esto permite:

- **Control de acceso** mediante login obligatorio
- **Gestión de usuarios** con diferentes niveles de permisos
- **Auditoría de acciones** - cada operación queda registrada con el usuario que la realizó
- **Cambio seguro de contraseñas** con hash SHA-256
- **Administración centralizada** de usuarios (solo para administradores)

---

## 🔐 Roles de Usuario

El sistema implementa tres niveles de acceso:

### 1. **Administrador** (`admin`)
- ✅ Acceso completo a todas las funciones
- ✅ Puede crear, editar y eliminar usuarios
- ✅ Puede cambiar roles y permisos
- ✅ Acceso al historial completo con información de usuarios

### 2. **Operador** (`operator`)
- ✅ Puede usar todas las funciones operativas del sistema
- ✅ Importar pedidos de SAP
- ✅ Generar e imprimir etiquetas GHS
- ✅ Ver historial de operaciones
- ✅ Consultar base de datos de productos
- ❌ No puede gestionar usuarios

### 3. **Visualizador** (`viewer`)
- ✅ Solo puede consultar información
- ✅ Ver historial
- ✅ Consultar base de datos
- ❌ No puede realizar cambios ni generar etiquetas
- ❌ No puede gestionar usuarios

---

## 🚀 Inicio del Sistema

### Primera Vez

Al iniciar el sistema por primera vez, se crea automáticamente una cuenta de administrador:

```
Usuario: admin
Contraseña: admin123
```

⚠️ **IMPORTANTE**: Debe cambiar esta contraseña inmediatamente después del primer inicio de sesión.

### Inicio de Sesión

1. Al ejecutar `./start` o `python3 ghs_label_gui.py`, aparecerá la ventana de login
2. Ingrese su usuario y contraseña
3. Presione "Iniciar Sesión" o Enter
4. Si es la primera vez con las credenciales por defecto, se le pedirá cambiar la contraseña

---

## 👥 Gestión de Usuarios (Solo Administradores)

### Acceder a la Gestión de Usuarios

En el menú lateral (sidebar), sección **USUARIO**:
- Click en **"👥 Gestionar Usuarios"**

### Crear Nuevo Usuario

1. En la ventana de Gestión de Usuarios, click en **"➕ Nuevo Usuario"**
2. Complete los campos:
   - **Usuario** *: Identificador único (mínimo 3 caracteres)
   - **Nombre Completo** *: Nombre real del usuario
   - **Email**: Correo electrónico (opcional)
   - **Rol** *: Seleccione el nivel de acceso
   - **Contraseña** *: Mínimo 6 caracteres
   - **Confirmar Contraseña** *: Debe coincidir
3. Click en **"Guardar"**

### Editar Usuario

1. Seleccione un usuario de la lista
2. Click en **"✏️ Editar"** o doble click en el usuario
3. Modifique los campos deseados
4. Click en **"Guardar"**

**Nota**: No se puede editar el nombre de usuario, solo los demás campos.

### Eliminar Usuario

1. Seleccione un usuario de la lista
2. Click en **"🗑️ Eliminar"**
3. Confirme la acción

**Restricciones**:
- No puede eliminarse a sí mismo
- Debe haber al menos un administrador en el sistema

### Activar/Desactivar Usuarios

Al editar un usuario, puede desmarcar "Usuario activo" para desactivarlo temporalmente sin eliminarlo.

---

## 🔑 Cambio de Contraseña

Cualquier usuario puede cambiar su propia contraseña:

1. En el menú lateral, sección **USUARIO**
2. Click en **"🔑 Cambiar Contraseña"**
3. Ingrese:
   - Contraseña actual
   - Nueva contraseña (mínimo 6 caracteres)
   - Confirmar nueva contraseña
4. Click en **"Guardar"**

---

## 📊 Auditoría y Historial

### Seguimiento de Acciones

Todas las operaciones críticas quedan registradas con:
- ✅ Fecha y hora exacta
- ✅ Usuario que realizó la acción
- ✅ Tipo de operación (SAP_IMPORT, IMPRESION, etc.)
- ✅ Detalles específicos de la operación

### Ver Historial

En la pestaña **"⧗ Historial"** del menú principal:
- Columna **"Usuario"** muestra quién realizó cada acción
- Use el campo de búsqueda para filtrar por usuario
- Click en encabezados de columna para ordenar

---

## 🔒 Seguridad

### Almacenamiento de Contraseñas

- Las contraseñas se almacenan con hash **SHA-256**
- Cada contraseña usa un **salt único** generado aleatoriamente
- El sistema nunca almacena contraseñas en texto plano
- Formato: `salt$hash`

### Sesión

- El usuario debe autenticarse al iniciar la aplicación
- La sesión permanece activa hasta cerrar la aplicación o hacer logout
- No hay timeout automático (sesión permanente durante ejecución)

### Cierre de Sesión

En el menú lateral, sección **USUARIO**:
- Click en **"🚪 Cerrar Sesión"**
- Confirme la acción
- La aplicación se reiniciará y pedirá nuevo login

---

## 📁 Archivos del Sistema

### Archivos Principales

- **`user_manager.py`**: Módulo central de gestión de usuarios
- **`login_dialog.py`**: Interfaz de login y cambio de contraseña
- **`user_management_dialog.py`**: Interfaz de administración de usuarios
- **`users.json`**: Base de datos de usuarios (⚠️ no editar manualmente)
- **`history.json`**: Registro de operaciones con información de usuarios

### Estructura de users.json

```json
{
  "users": [
    {
      "username": "admin",
      "password_hash": "salt$hash",
      "role": "admin",
      "full_name": "Administrator",
      "email": "",
      "created_at": "2026-01-19T...",
      "last_login": "2026-01-19T...",
      "is_active": true,
      "must_change_password": false
    }
  ]
}
```

---

## 🛠️ Uso Programático

### Importar Módulos

```python
from user_manager import UserManager, UserRole
from login_dialog import LoginDialog, PasswordChangeDialog
from user_management_dialog import UserManagementDialog
```

### Autenticar Usuario

```python
um = UserManager("users.json")

# Verificar credenciales
if um.authenticate("username", "password"):
    user = um.get_current_user()
    print(f"Welcome {user['full_name']}")
else:
    print("Invalid credentials")
```

### Verificar Permisos

```python
# Verificar si el usuario actual tiene permiso de admin
if um.has_permission(UserRole.ADMIN):
    print("User is admin")

# Verificar si puede realizar operaciones
if um.has_permission(UserRole.OPERATOR):
    print("User can operate the system")
```

### Crear Usuario

```python
success, msg = um.create_user(
    username="newuser",
    password="securepass",
    role=UserRole.OPERATOR,
    full_name="John Doe",
    email="john@example.com"
)

if success:
    print(msg)  # "User 'newuser' created successfully"
```

### Actualizar Usuario

```python
# Cambiar contraseña
success, msg = um.update_user("username", password="newpass")

# Cambiar rol (solo admin)
success, msg = um.update_user("username", role=UserRole.ADMIN)

# Desactivar usuario
success, msg = um.update_user("username", is_active=False)
```

### Listar Usuarios

```python
users = um.list_users()
for user in users:
    print(f"{user['username']}: {user['role']}")
```

---

## 🆘 Resolución de Problemas

### No puedo iniciar sesión

1. Verifique que está usando las credenciales correctas
2. Si es la primera vez, use: `admin` / `admin123`
3. Verifique que el archivo `users.json` no esté corrupto

### Olvidé la contraseña de admin

Si pierde la contraseña del administrador:

1. Detenga la aplicación
2. Elimine el archivo `users.json`
3. Reinicie la aplicación - se creará un nuevo admin por defecto
4. Use: `admin` / `admin123`
5. Cambie la contraseña inmediatamente

### Error al crear usuario

- El nombre de usuario debe tener al menos 3 caracteres
- Las contraseñas deben tener al menos 6 caracteres
- Los nombres de usuario deben ser únicos

### No veo la opción de gestionar usuarios

- Solo los usuarios con rol **Administrador** pueden ver esta opción
- Verifique su rol actual en la sección USUARIO del menú lateral

---

## 📝 Registro de Cambios

### Versión 1.0 (Enero 2026)

**Características Nuevas**:
- ✅ Sistema completo de autenticación de usuarios
- ✅ Tres niveles de permisos (Admin, Operador, Visualizador)
- ✅ Interfaz de gestión de usuarios para administradores
- ✅ Seguimiento de acciones por usuario en historial
- ✅ Cambio seguro de contraseñas con hash SHA-256
- ✅ Sesiones persistentes durante ejecución
- ✅ Cierre de sesión con reinicio de aplicación

**Archivos Modificados**:
- `ghs_label_gui.py`: Integración de autenticación
- `history_manager.py`: Soporte para tracking de usuarios

**Archivos Nuevos**:
- `user_manager.py`: Core de gestión de usuarios
- `login_dialog.py`: Interfaz de login
- `user_management_dialog.py`: Interfaz de administración
- `users.json`: Base de datos de usuarios

---

## 📞 Soporte

Para más información o reportar problemas:
- Contacte al administrador del sistema
- Revise los logs de la aplicación
- Consulte el código fuente en los archivos mencionados

---

**Sistema SGA v1.0 con Control de Usuarios**  
*Gestión de Etiquetas GHS - Quimica Boss*
