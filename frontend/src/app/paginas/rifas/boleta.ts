/** Boleta "F012-07": código del talonario y número de la boleta dentro de él (dos dígitos). */
export function boleta(codigo: string, numero: number): string {
  return `${codigo}-${String(numero).padStart(2, '0')}`;
}
