-- Ingestar personas extraídas del contenido de cada aviso
-- Patrón 1: apellidos en mayúsculas sostenidas (ej: MANUSOVICH, GARRIDO)
INSERT INTO entidades.entidades (id, nombre, tipo)
SELECT nextval('entidades_seq'), nombre, 'persona'
FROM (
    SELECT DISTINCT regexp_extract_all(
        CASE WHEN POSITION('OBJETO' IN contenido) > 0 
             THEN SUBSTRING(contenido, 1, POSITION('OBJETO' IN contenido)) 
             ELSE contenido 
        END, 
    '([A-ZÁÉÍÓÚÑ][a-záéíóúñ]*(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]*)*\s+[A-ZÁÉÍÓÚÑ]{3,}(?:\s+[A-ZÁÉÍÓÚÑ]{3,})?)\s*(?:\([^)]*\))?\s*[,;]', 1) AS nombres
    FROM bronze.boletin_sa_constitucion
) t, LATERAL UNNEST(t.nombres) AS u(nombre)
WHERE u.nombre NOT ILIKE '%SOCIOS%'
  AND u.nombre NOT ILIKE '%ADUANAS%'
  AND u.nombre NOT ILIKE '%BUENOS AIRES%'
  AND u.nombre NOT ILIKE '%PROVINCIA%'
  AND u.nombre NOT ILIKE '%ESTATUTOS%'
  AND u.nombre NOT ILIKE '%EXTRANJERO%'
  AND u.nombre NOT ILIKE '%INGENIERO%'
  AND u.nombre NOT ILIKE '%COUNTRY%'
  AND u.nombre NOT ILIKE '%PUNTA%'
  AND u.nombre NOT ILIKE '%ACCIONISTAS%'
  AND u.nombre NOT ILIKE '%BARRIO%'
  AND u.nombre NOT ILIKE '%AFIP%'
  AND LENGTH(u.nombre) < 60
ON CONFLICT (nombre, tipo) DO NOTHING;

-- Patrón 2: nombres mixtos seguidos de DNI o nacionalidad
INSERT INTO entidades.entidades (id, nombre, tipo)
SELECT nextval('entidades_seq'), nombre, 'persona'
FROM (
    SELECT DISTINCT regexp_extract_all(
        CASE WHEN POSITION('OBJETO' IN contenido) > 0 
             THEN SUBSTRING(contenido, 1, POSITION('OBJETO' IN contenido)) 
             ELSE contenido 
        END,
    '([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+?)\s*,\s*(?:DNI\b|argentino|argentina|uruguayo|venezolano)', 1) AS nombres
    FROM bronze.boletin_sa_constitucion
) t, LATERAL UNNEST(t.nombres) AS u(nombre)
WHERE u.nombre NOT ILIKE '%SOCIOS%'
  AND u.nombre NOT ILIKE '%ACCIONISTAS%'
  AND LENGTH(u.nombre) < 60
ON CONFLICT (nombre, tipo) DO NOTHING;

SELECT COUNT(*) AS total_entidades FROM entidades.entidades;
SELECT tipo, COUNT(*) AS cantidad FROM entidades.entidades GROUP BY tipo ORDER BY tipo;
