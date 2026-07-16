# SGA Web Application

Web version of the GHS Label System (Sistema Global Armonizado) for warehouse operations.

## Features

- 🏷️ **Label Generation** - Generate GHS-compliant labels for chemical products
- 📦 **SAP Integration** - Load orders directly from SAP Business One
- 📊 **Order Status Tracking** - Track order status through fulfillment
- 👥 **User Management** - Role-based access control (Admin/Operator/Viewer)
- 🔍 **Product Database** - Browse and search chemical products
- 📱 **Responsive Design** - Works on desktop and mobile

## Quick Start

### Windows
```batch
cd sga_web
run.bat
```

### Linux/Mac
```bash
cd sga_web
chmod +x run.sh
./run.sh
```

Then open http://localhost:5000 in your browser.

**Default Credentials:** admin / admin123

## Docker Deployment

```bash
cd sga_web
docker-compose up -d
```

## Project Structure

```
sga_web/
├── app.py              # Flask application entry point
├── config.py           # Configuration settings
├── models.py           # User and data models
├── requirements.txt    # Python dependencies
├── routes/             # Route blueprints
│   ├── auth.py        # Authentication routes
│   ├── main.py        # Dashboard routes
│   ├── labels.py      # Label generation routes
│   ├── products.py    # Product database routes
│   ├── orders.py      # Order status routes
│   └── api.py         # REST API endpoints
└── templates/          # Jinja2 HTML templates
    ├── base.html      # Base template with sidebar
    ├── dashboard.html # Main dashboard
    ├── auth/          # Login/password templates
    ├── labels/        # Label generation UI
    ├── products/      # Product browser
    ├── orders/        # Order status tracking
    └── errors/        # Error pages
```

## Reused Backend Modules

This web app reuses the following modules from the original Tkinter application:

| Module | Purpose |
|--------|---------|
| `smart_label.py` | GHS data resolution + database connection |
| `generate_ghs_label.py` | ReportLab PDF generation |
| `user_manager.py` | Authentication with roles |
| `history_manager.py` | Activity logging |
| `order_status_manager.py` | Order tracking |
| `settings_manager.py` | Configuration management |
| `sap_connector.py` | SAP HANA integration (optional) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/products` | GET | List products (paginated) |
| `/api/products/<code>` | GET | Get single product |
| `/api/orders` | GET | List orders |
| `/api/orders/<id>` | GET | Get single order |
| `/api/stats` | GET | Dashboard statistics |
| `/api/history` | GET | Activity history |
| `/labels/queue/add` | POST | Add item to print queue |
| `/labels/generate` | POST | Generate label PDFs |

## Configuration

Environment variables:
- `FLASK_ENV` - development/production
- `SECRET_KEY` - Session secret key
- `SAP_HOST` - SAP HANA server (default: 20.0.1.9)
- `SAP_PORT` - SAP HANA port (default: 30015)

## Technology Stack

- **Backend:** Python 3.10+, Flask 3.0
- **Frontend:** Tailwind CSS, Alpine.js
- **PDF:** ReportLab
- **Database:** CSV-based (unified_db)
- **Optional:** SAP HANA via hdbcli
