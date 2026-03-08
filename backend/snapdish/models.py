"""
SQLAlchemy ORM models for SnapDish.

Tables:
  users                  — identity record (external auth provider links to this)
  user_dietary_profiles  — server-side dietary constraints (non-tamperable)
  cached_meals           — meals cached from external food APIs
  cached_ingredients     — ingredients with nutrition data cached from USDA FDC
  meal_dietary_tags      — many-to-many: meals × dietary tag
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Application user. user_id is a stable external identifier (e.g. UUID from auth provider)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), unique=True, nullable=False, index=True)
    email_hash = Column(String(64), nullable=True)  # SHA-256 of email, never plain email
    created_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime, nullable=False, server_default=text("NOW()"), onupdate=datetime.utcnow)

    dietary_profile = relationship(
        "UserDietaryProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserDietaryProfile(Base):
    """
    Server-side dietary constraints. NEVER populated from client request body.
    Populated only via authenticated profile update endpoints or admin.

    allergy_tags: JSON list of strings from ALLERGY_TAGS enum.
    restriction_tags: JSON list of strings from RESTRICTION_TAGS enum.
    condition_tags: JSON list of strings from CONDITION_TAGS enum.
    custom_notes: free-text notes reviewed by support (optional).
    """

    __tablename__ = "user_dietary_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(128),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Structured tags stored as JSON arrays for portability
    allergy_tags = Column(JSON, nullable=False, default=list)       # ["peanuts", "dairy", ...]
    restriction_tags = Column(JSON, nullable=False, default=list)   # ["vegan", "halal", ...]
    condition_tags = Column(JSON, nullable=False, default=list)     # ["diabetes", "celiac", ...]
    disliked_ingredients = Column(JSON, nullable=False, default=list)  # ["cilantro", ...]
    preferred_cuisines = Column(JSON, nullable=False, default=list)    # ["italian", "mexican", ...]

    custom_notes = Column(Text, nullable=True)  # Short free-text, max 500 chars

    updated_at = Column(DateTime, nullable=False, server_default=text("NOW()"), onupdate=datetime.utcnow)

    user = relationship("User", back_populates="dietary_profile")


class CachedMeal(Base):
    """
    Meals fetched from external food APIs and cached locally.
    source: "spoonacular" | "openfoodfacts" | "usdafdc" | "manual"
    """

    __tablename__ = "cached_meals"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_meal_source_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(32), nullable=False, index=True)
    source_id = Column(String(64), nullable=False)
    name = Column(String(512), nullable=False, index=True)
    cuisine_tags = Column(JSON, nullable=False, default=list)   # ["italian", "mediterranean"]
    dietary_tags = Column(JSON, nullable=False, default=list)   # ["vegan", "gluten-free"]
    ingredient_names = Column(JSON, nullable=False, default=list)  # ["pasta", "eggs", ...]
    calories_kcal = Column(Float, nullable=True)
    protein_g = Column(Float, nullable=True)
    carbs_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    fiber_g = Column(Float, nullable=True)
    sodium_mg = Column(Float, nullable=True)
    image_url = Column(String(1024), nullable=True)
    source_url = Column(String(1024), nullable=True)
    raw_json = Column(JSON, nullable=True)  # Original API response (for re-processing)
    cached_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
    is_active = Column(Boolean, nullable=False, default=True)

    @property
    def summary(self) -> dict:
        return {
            "name": self.name,
            "cuisine_tags": self.cuisine_tags,
            "dietary_tags": self.dietary_tags,
            "calories_kcal": self.calories_kcal,
            "protein_g": self.protein_g,
            "carbs_g": self.carbs_g,
            "fat_g": self.fat_g,
            "source": self.source,
            "image_url": self.image_url,
        }


class CachedIngredient(Base):
    """
    Ingredient nutritional data cached from USDA FoodData Central.
    Keyed by fdcId; name is descriptive for text lookup.
    """

    __tablename__ = "cached_ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fdc_id = Column(Integer, unique=True, nullable=True, index=True)
    name = Column(String(512), nullable=False, index=True)
    calories_per_100g = Column(Float, nullable=True)
    protein_per_100g = Column(Float, nullable=True)
    carbs_per_100g = Column(Float, nullable=True)
    fat_per_100g = Column(Float, nullable=True)
    fiber_per_100g = Column(Float, nullable=True)
    sodium_per_100mg = Column(Float, nullable=True)
    food_category = Column(String(128), nullable=True)
    raw_json = Column(JSON, nullable=True)
    cached_at = Column(DateTime, nullable=False, server_default=text("NOW()"))


# ---------------------------------------------------------------------------
# Controlled vocabulary (kept in code, not DB, so guardrails can't be altered)
# ---------------------------------------------------------------------------

ALLERGY_TAGS = frozenset(
    [
        "peanuts",
        "tree_nuts",
        "dairy",
        "eggs",
        "wheat",
        "gluten",
        "soy",
        "fish",
        "shellfish",
        "sesame",
        "mustard",
        "sulphites",
        "celery",
        "lupin",
        "molluscs",
    ]
)

RESTRICTION_TAGS = frozenset(
    [
        "vegan",
        "vegetarian",
        "pescatarian",
        "halal",
        "kosher",
        "raw_food",
        "paleo",
        "keto",
        "low_fodmap",
    ]
)

CONDITION_TAGS = frozenset(
    [
        "diabetes_type1",
        "diabetes_type2",
        "prediabetes",
        "celiac",
        "crohns",
        "ibs",
        "hypertension",
        "heart_disease",
        "kidney_disease",
        "gout",
        "phenylketonuria",
        "pregnancy",
        "immunocompromised",
    ]
)


class GuardrailRule(Base):
    """
    Operator-managed guardrail rules stored in the database.
    Only writable by operators (admin tools / migrations) — never by the API.
    The API reads these at startup and caches them in memory (guardrails.py).

    scope:   "input"  — checked before model receives user text
             "output" — checked after model returns text
             "search" — checked before any web search query is submitted
    pattern: Python regex (re.compile with IGNORECASE | DOTALL)
    """

    __tablename__ = "guardrail_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True, index=True)
    scope = Column(String(16), nullable=False, index=True)   # "input" | "output" | "search"
    pattern = Column(Text, nullable=False)                    # Python regex string
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime, nullable=False, server_default=text("NOW()"), onupdate=datetime.utcnow)
