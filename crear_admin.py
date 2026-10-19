from getpass import getpass
import re

from sqlalchemy import select

from auth_security import hash_password
from database import SessionLocal
from models import User
from schema_updates import initialize_schema


def main() -> None:
    initialize_schema()
    db = SessionLocal()
    try:
        existing_admin = db.scalar(select(User).where(User.role == "admin").order_by(User.id))
        if existing_admin is not None:
            confirm_reset = input(
                f"Ya existe un administrador ({existing_admin.email}). "
                "¿Quieres restablecer sus credenciales? [s/N]: "
            ).strip().lower()
            if confirm_reset not in {"s", "si", "sí", "y", "yes"}:
                print("No se realizaron cambios.")
                return

        identifier = input("Usuario admin o correo del administrador [admin]: ").strip().lower() or "admin"
        if identifier != "admin" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", identifier):
            raise SystemExit("Usa admin o escribe un correo válido.")
        existing_identifier = db.scalar(select(User).where(User.email == identifier))
        if existing_identifier is not None and existing_identifier.id != getattr(existing_admin, "id", None):
            raise SystemExit("Ese usuario/correo ya está registrado con otro rol.")

        min_length = 1 if identifier == "admin" else 8
        hint = "Contraseña temporal: " if identifier == "admin" else "Contraseña (mínimo 8 caracteres): "
        password = getpass(hint)
        confirmation = getpass("Confirma la contraseña: ")
        if len(password) < min_length:
            raise SystemExit(f"La contraseña debe tener al menos {min_length} caracteres.")
        if password != confirmation:
            raise SystemExit("Las contraseñas no coinciden.")

        if existing_admin is not None:
            existing_admin.email = identifier
            existing_admin.password_hash = hash_password(password)
            existing_admin.is_active = True
        else:
            db.add(User(email=identifier, password_hash=hash_password(password), role="admin", is_active=True))
        db.commit()
        print(f"Credenciales de administrador guardadas para: {identifier}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
