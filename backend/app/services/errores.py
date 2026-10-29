"""Errores de reglas de negocio. El mensaje se muestra tal cual al usuario (main.py los convierte en HTTP)."""


class ErrorNegocio(Exception):
    status_code = 422


class NoEncontrado(ErrorNegocio):
    status_code = 404


class Conflicto(ErrorNegocio):
    status_code = 409


class Prohibido(ErrorNegocio):
    status_code = 403
