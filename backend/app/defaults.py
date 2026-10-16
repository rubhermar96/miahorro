"""Starting categories for a new user, adapted to Spain (RF-MOV-02). Users can rename,
archive or add to them; they are created only once."""

from sqlalchemy.orm import Session

from app import clock
from app.models.transactions import Category
from app.models.user import User

# (kind, name, icon, subcategories)
DEFAULT_CATEGORIES: list[tuple[str, str, str, list[str]]] = [
    (
        "expense",
        "Vivienda",
        "🏠",
        [
            "Alquiler o hipoteca",
            "Comunidad",
            "Luz",
            "Agua",
            "Gas",
            "Internet y móvil",
            "Seguro de hogar",
            "IBI y tasas",
            "Reparaciones",
        ],
    ),
    (
        "expense",
        "Alimentación",
        "🛒",
        ["Supermercado", "Restaurantes", "Cafeterías y bares", "Comida a domicilio"],
    ),
    (
        "expense",
        "Transporte",
        "🚗",
        [
            "Combustible",
            "Transporte público",
            "Taxi y VTC",
            "Parking y peajes",
            "Mantenimiento del coche",
            "Seguro del coche",
        ],
    ),
    ("expense", "Salud", "💊", ["Farmacia", "Médico y dentista", "Seguro médico", "Óptica"]),
    (
        "expense",
        "Ocio",
        "🎉",
        ["Suscripciones", "Viajes", "Cultura y espectáculos", "Deporte", "Aficiones"],
    ),
    ("expense", "Compras", "🛍️", ["Ropa y calzado", "Tecnología", "Hogar y decoración", "Regalos"]),
    ("expense", "Cuidado personal", "💇", ["Peluquería y estética"]),
    ("expense", "Educación", "📚", ["Formación", "Libros y material"]),
    ("expense", "Familia", "🧸", ["Hijos", "Mascotas"]),
    (
        "expense",
        "Finanzas",
        "💳",
        ["Comisiones bancarias", "Intereses de préstamos", "Impuestos"],
    ),
    ("expense", "Otros gastos", "📦", []),
    ("income", "Nómina", "💼", []),
    ("income", "Ingresos extra", "✨", []),
    ("income", "Intereses y dividendos", "📈", []),
    ("income", "Devoluciones", "↩️", []),
    ("income", "Regalos recibidos", "🎁", []),
    ("income", "Otros ingresos", "💰", []),
]


def ensure_default_categories(db: Session, user: User) -> None:
    """Create the starting categories the first time a user needs them."""
    if user.categories_seeded_at is not None:
        return
    for kind, name, icon, children in DEFAULT_CATEGORIES:
        parent = Category(user_id=user.id, kind=kind, name=name, icon=icon)
        db.add(parent)
        db.flush()
        for child in children:
            db.add(Category(user_id=user.id, kind=kind, name=child, parent_id=parent.id))
    user.categories_seeded_at = clock.now()
    db.commit()
