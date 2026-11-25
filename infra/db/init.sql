-- Extensiones necesarias para el despliegue con PostgreSQL.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Zona horaria por defecto (las columnas son timestamptz).
ALTER DATABASE nutririsk SET timezone TO 'UTC';
