# Quick Reference: Styled Dialogs

## Import
```python
from styled_dialogs import StyledMessageBox
```

## Usage

### Information Dialog (Blue ℹ️)
```python
StyledMessageBox.showinfo("Título", "Mensaje informativo", parent=window)
```

### Success Dialog (Green ✓)
```python
StyledMessageBox.showsuccess("Éxito", "Operación completada", parent=window)
```

### Error Dialog (Red ✕)
```python
StyledMessageBox.showerror("Error", "Algo salió mal", parent=window)
```

### Warning Dialog (Orange ⚠)
```python
StyledMessageBox.showwarning("Advertencia", "Revise los datos", parent=window)
```

### Yes/No Question (Purple ❔)
```python
if StyledMessageBox.askyesno("Confirmar", "¿Continuar?", parent=window):
    # User clicked "Sí"
    do_action()
else:
    # User clicked "No"
    cancel_action()
```

### OK/Cancel Dialog
```python
if StyledMessageBox.askokcancel("Confirmar", "Guardar cambios?", parent=window):
    save_changes()
```

## Common Patterns

### Delete Confirmation
```python
if StyledMessageBox.askyesno(
    "Confirmar Eliminación",
    f"¿Está seguro de eliminar '{item_name}'?\n\nEsta acción no se puede deshacer.",
    parent=self.window
):
    delete_item()
    StyledMessageBox.showsuccess("Éxito", "Elemento eliminado", parent=self.window)
```

### Password Change Confirmation
```python
if StyledMessageBox.askyesno(
    "Cambio de Contraseña",
    "Por seguridad, debe cambiar su contraseña.\n\n¿Desea cambiarla ahora?",
    parent=self.dialog
):
    change_password()
    StyledMessageBox.showsuccess("Éxito", "Contraseña actualizada", parent=self.dialog)
```

### Save with Validation
```python
try:
    save_data()
    StyledMessageBox.showsuccess("Guardado", "Datos guardados correctamente", parent=self.window)
except ValidationError as e:
    StyledMessageBox.showwarning("Validación", str(e), parent=self.window)
except Exception as e:
    StyledMessageBox.showerror("Error", f"No se pudo guardar:\n{e}", parent=self.window)
```

## Tips

- **Always pass parent window** for proper centering and modal behavior
- **Use multiline messages** with `\n` for better readability
- **Keep titles short** (1-3 words) - descriptive but concise
- **Choose the right type**: 
  - Info/Success for confirmations
  - Warning for validation issues
  - Error for failures
  - Question for confirmations that need user choice

## Button Behavior

- **Enter key** = Primary button (Yes/OK/Aceptar)
- **Escape key** = Cancel/close
- **Tab key** = Navigate between buttons
- **Mouse hover** = Visual feedback
