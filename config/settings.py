"""
Configuration Django du projet PharmaGest.

Les valeurs sensibles (cle secrete, base de donnees, hote autorise) sont lues
dans l'environnement. Un fichier .env a la racine du projet est charge
automatiquement en developpement (voir .env.example).
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _charger_env(fichier):
    """Charge un fichier .env simple sans dependance externe."""
    if not fichier.exists():
        return
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        cle = cle.strip()
        valeur = valeur.strip().strip('"').strip("'")
        os.environ.setdefault(cle, valeur)


_charger_env(BASE_DIR / ".env")


def env_bool(nom, defaut=False):
    valeur = os.environ.get(nom)
    if valeur is None:
        return defaut
    return valeur.strip().lower() in {"1", "true", "oui", "yes", "on"}


def env_liste(nom, defaut=""):
    valeur = os.environ.get(nom, defaut)
    return [element.strip() for element in valeur.split(",") if element.strip()]


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-developpement-pharmagest-a-remplacer-en-production",
)

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_liste("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

CSRF_TRUSTED_ORIGINS = env_liste("DJANGO_CSRF_TRUSTED_ORIGINS", "")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "utilisateurs",
    "medicaments",
    "fournisseurs",
    "clients",
    "achats",
    "stock",
    "ventes",
    "rapports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "rapports.context_processors.pharmacie",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Base de donnees : SQLite par defaut, PostgreSQL en production.
if os.environ.get("DB_ENGINE", "").lower() in {"postgres", "postgresql", "django.db.backends.postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "pharmagest"),
            "USER": os.environ.get("DB_USER", "pharmagest"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_USER_MODEL = "utilisateurs.Utilisateur"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "utilisateurs:connexion"
LOGIN_REDIRECT_URL = "tableau_bord"
LOGOUT_REDIRECT_URL = "utilisateurs:connexion"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Durcissement HTTPS automatique hors developpement.
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Informations affichees sur les documents PDF.
PHARMACIE = {
    "nom": os.environ.get("PHARMACIE_NOM", "Pharmacie PharmaGest"),
    "adresse": os.environ.get("PHARMACIE_ADRESSE", "Avenue de la Sante, Abidjan"),
    "telephone": os.environ.get("PHARMACIE_TELEPHONE", "+225 00 00 00 00"),
    "email": os.environ.get("PHARMACIE_EMAIL", "contact@pharmagest.local"),
    "devise": os.environ.get("PHARMACIE_DEVISE", "FCFA"),
}

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
