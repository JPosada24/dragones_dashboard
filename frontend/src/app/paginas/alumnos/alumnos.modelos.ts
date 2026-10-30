import { EstadoCuenta } from '../resumen/resumen.modelos';

export type { EstadoCuenta };
export type Rama = 'masculina' | 'femenina';

export interface AcudienteVinculado {
  acudiente_id: string;
  nombres: string;
  apellidos: string;
  telefono: string;
  parentesco: string;
  principal: boolean;
}

export interface Alumno {
  id: string;
  nombres: string;
  apellidos: string;
  tipo_documento: string;
  documento: string; // enmascarado: ****1234
  fecha_nacimiento: string;
  edad: number;
  es_menor: boolean;
  rama: Rama;
  telefono: string | null;
  email: string | null;
  direccion: string | null;
  eps: string | null;
  usuario_id: string | null;
  activo: boolean;
  inscripcion_estado: string | null;
  acudientes: AcudienteVinculado[];
}

export interface Acudiente {
  id: string;
  nombres: string;
  apellidos: string;
  tipo_documento: string;
  documento: string; // enmascarado
  telefono: string;
  email: string | null;
}

export interface Documento {
  id: string;
  tipo: string;
  nombre_original: string;
  mime: string;
  tamano: number;
  creado_en: string;
}

export interface RegistroHistorial {
  sesion_id: string;
  fecha: string;
  hora_inicio: string;
  estado: 'presente' | 'ausente' | 'justificado';
  multa_valor: number | null;
  multa_estado: 'pendiente' | 'pagada' | 'anulada' | null;
}
