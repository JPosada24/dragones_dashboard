# 0005. WhatsApp con enlaces wa.me, sin API de Meta ni bots

- **Estado:** aceptada

## Contexto

Las familias usan WhatsApp, pero la API oficial de Meta cuesta por mensaje y los bots no oficiales de WhatsApp Web violan los términos y arriesgan el bloqueo del número del club.

## Decisión

La plataforma prepara el mensaje y el enlace `wa.me/<número>?text=…`; el staff lo abre y lo envía desde el número del club. Lo automático va por correo (Gmail con contraseña de aplicación) y por la bandeja de la plataforma. La interfaz de notificaciones deja lista la puerta para otro proveedor.

## Consecuencias

- Costo cero y sin riesgo para el número del club.
- Requiere un clic del staff por mensaje; la cola de «Avisos» lo hace rápido.
- El enlace se valida antes de abrirlo (solo `https://wa.me/<número>?text=`).
