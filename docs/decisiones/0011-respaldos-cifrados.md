# 0011. Copias de seguridad cifradas con clave pública

- **Estado:** aceptada

## Contexto

Las copias contienen datos de menores. Si el servidor se ve comprometido, las copias guardadas en él (o en el almacenamiento externo) no deberían ser legibles.

## Decisión

Cada copia (pg_dump + archivos) se cifra con la clave **pública** de age; la privada vive fuera del servidor. Rotación 7 diarias / 4 semanales / 6 mensuales y sincronización opcional con rclone. `restaurar.sh` verifica antes de reemplazar y exige `CONFIRMAR=si`.

## Consecuencias

- El servidor crea copias que él mismo no puede leer.
- Restaurar exige traer la clave privada: a propósito.
- El simulacro de restauración se probó de punta a punta (conteos y archivos idénticos).
