# GHS Label Print Agent
<br>
Servicio local ligero que imprime etiquetas GHS directamente a la impresora USB,
**sin pasar por el diálogo de impresión de Chrome**.

## ¿Por qué?

Chrome no respeta correctamente el tamaño personalizado de papel (200×150mm) al imprimir,
causando que las etiquetas se corten o escalen mal. Este agente recibe las imágenes de
etiquetas desde la aplicación web y las envía directamente a la impresora con las
dimensiones exactas.

## Arquitectura

```
Navegador (PC Almacén)  ──fetch──▶  Flask Server (genera imágenes)
          │
          └──fetch──▶  localhost:5555 (Print Agent) ──USB──▶  EPSON L4150
```

## Instalación Rápida

### 1. Instalar dependencias (una sola vez)

```bash
cd print_agent
pip install -r requirements.txt
```

O ejecutar `install.bat`.

### 2. Configurar impresora (opcional)

Editar `print_agent_config.json`:
```json
{
    "printer_name": "EPSON L4150 Series",
    "port": 5555
}
```

Si `printer_name` está vacío, usa la impresora predeterminada del sistema.

### 3. Iniciar el agente

```bash
python print_agent.py
```

O ejecutar `start_agent.bat`.

## Uso

1. Iniciar el Print Agent en la PC del almacén (`start_agent.bat`)
2. Abrir la aplicación web SGA en Chrome
3. En la cola de etiquetas, verás un indicador verde "EPSON L4150..." si el agente está conectado
4. Usar el botón **⚡ Impresión Directa** (verde) para imprimir sin diálogo
5. El botón azul **Imprimir** sigue disponible como respaldo (usa Chrome)

## Endpoints API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/status` | Estado del agente + impresora |
| POST | `/print` | Imprimir imágenes (JSON con base64) |
| GET | `/printers` | Listar impresoras disponibles |
| POST | `/test` | Imprimir página de prueba |
| GET/POST | `/configure` | Ver/cambiar configuración |

### Ejemplo: Imprimir una imagen

```bash
curl -X POST http://localhost:5555/print \
  -H "Content-Type: application/json" \
  -d '{"image_base64": "<base64_data>", "width_mm": 200, "height_mm": 150}'
```

## Opciones de línea de comandos

```
python print_agent.py --port 5555         # Puerto personalizado
python print_agent.py --printer "EPSON"   # Impresora específica
python print_agent.py --list-printers     # Listar impresoras y salir
python print_agent.py --debug             # Modo debug
```

## Configuración

`print_agent_config.json`:

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `printer_name` | string | `""` | Nombre de impresora (vacío = default) |
| `port` | int | `5555` | Puerto HTTP |
| `default_width_mm` | int | `200` | Ancho etiqueta (mm) |
| `default_height_mm` | int | `150` | Alto etiqueta (mm) |
| `auto_orient` | bool | `true` | Auto-detectar orientación |
| `log_level` | string | `"INFO"` | Nivel de log |

## Solución de Problemas

| Problema | Solución |
|----------|----------|
| "Print Agent no disponible" | Verificar que `start_agent.bat` esté corriendo |
| Imprime en impresora incorrecta | Configurar `printer_name` en config.json |
| El tamaño de la etiqueta es incorrecto | Verificar `default_width_mm` / `default_height_mm` |
| Error "pywin32 not found" | Ejecutar `pip install pywin32` |
| No se instala correctamente | Ejecutar `install.bat` como Administrador |
