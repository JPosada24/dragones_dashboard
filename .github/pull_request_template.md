## Qué cambia y por qué

<!-- Una o dos frases. Si cierra un issue: "Cierra #12". -->

## Cómo se probó

- [ ] Pruebas del backend (`pytest`) y del frontend (`ng test --coverage`) en verde
- [ ] Prueba nueva para cada regla nueva, incluida la de permisos (qué rol **no** puede)
- [ ] Si cambió la API: contrato OpenAPI y tipos del frontend regenerados
- [ ] Si cambió el esquema: migración Alembic nueva (no se edita una aplicada)

## Seguridad

- [ ] Autorización en el servidor (`requiere`) y alcance en el servicio; recurso ajeno → 404
- [ ] Sin secretos ni datos reales del club en el código, las pruebas o las capturas
- [ ] Datos sensibles fuera de la auditoría y de los logs
