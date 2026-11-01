# 0003. Documentos cifrados en reposo con índice ciego

- **Estado:** aceptada

## Contexto

La plataforma guarda documentos de identidad de menores y archivos (copias de documentos, certificados). Hay que poder buscar a un alumno por su documento y evitar duplicados sin guardar el número en claro.

## Decisión

El número se cifra con Fernet (AES + HMAC) y se guarda además un HMAC determinístico (índice ciego) para buscar por igualdad. En pantalla solo se ven los últimos cuatro dígitos; el completo lo ven Admin y SuperAdmin y cada consulta queda auditada. Los archivos se cifran igual. `DATA_ENCRYPTION_KEY` admite varias claves (MultiFernet) para rotarla con `app.scripts.rotar_clave`.

## Consecuencias

- Una copia de la base filtrada no expone documentos sin la clave.
- No hay búsqueda parcial por documento (solo exacta): es el precio del índice ciego.
- Si se pierde la clave, esos datos no se recuperan: está documentado y se respalda aparte.
