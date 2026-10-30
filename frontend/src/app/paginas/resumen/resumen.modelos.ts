export interface ResumenStaff {
  indicadores: {
    alumnos_activos: number;
    alumnos_sin_inscripcion: number;
    inscripciones_pendientes: number;
    inscripciones_vencen_pronto: number;
    multas_pendientes: number;
    multas_saldo: number;
    alertas: number;
  };
  alertas: { tipo: string; titulo: string; detalle: string; cuando: string; ruta: string }[];
  hoy: {
    id: string;
    lugar: string | null;
    horario: string;
    cerrada: boolean;
    esperados: number;
    presentes: number;
    justificados: number;
    ausentes: number;
    sin_marcar: number;
  }[];
  rifas: { id: string; nombre: string; estado: string; fecha_sorteo: string; talonarios: number; pagados: number }[];
  cartera: { concepto: string; nota: string; monto: number }[];
  proximo_torneo: {
    id: string;
    nombre: string;
    rama: string;
    fecha_inicio: string;
    fecha_fin: string;
    lugar: string | null;
    ocupados: number;
    cupo: number;
  } | null;
}

export interface AlumnoBasico {
  id: string;
  nombres: string;
  apellidos: string;
  rama: string;
  es_menor: boolean;
}

export interface EstadoCuenta {
  alumno_id: string;
  inscripcion_estado: string | null;
  inscripcion_saldo: number;
  multas_pendientes: number;
  multas_saldo: number;
  rifas: { rifa: string; saldo: number }[];
  total: number;
  al_dia: boolean;
  en_mora: boolean;
  entra_en_mora: string | null;
}

export interface SesionBasica {
  id: string;
  fecha: string;
  hora_inicio: string;
  hora_fin: string;
  lugar: string | null;
  cancelada: boolean;
}
