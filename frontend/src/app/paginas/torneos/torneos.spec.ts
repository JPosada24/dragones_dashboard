import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { isoLocal, sumarDias } from '../../compartido/fechas';
import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { gruposSugeridos } from './grupos-torneo';
import { TorneosPage } from './torneos';
import { Equipo, SorteoGrupos, Torneo } from './torneos.modelos';

registerLocaleData(localeEsCo);

const HOY = new Date();
const ADMIN = ['eventos.gestionar', 'pagos.registrar'];
const SUPERADMIN = [...ADMIN, 'pagos.anular'];

const torneo = (id: string, extra: Partial<Torneo> = {}): Torneo => ({
  id, nombre: `Copa ${id}`, rama: 'femenina', fecha_inicio: isoLocal(sumarDias(HOY, 20)), fecha_fin: isoLocal(sumarDias(HOY, 21)),
  jornadas: [{ rama: 'femenina', fecha: isoLocal(sumarDias(HOY, 20)), sedes: [] }],
  fecha_limite_inscripcion: isoLocal(sumarDias(HOY, 10)), inscripcion_hasta: isoLocal(sumarDias(HOY, 10)),
  lugar: 'Coliseo', cupo_equipos: 2, valor_inscripcion: 150000,
  estado: 'programado', motivo_cancelacion: null, ocupados: 2, confirmados: 1, en_espera: 1, recaudado: 200000, ...extra,
});

const equipo = (id: string, extra: Partial<Equipo> = {}): Equipo => ({
  id, nombre_club: `Club ${id}`, rama: 'femenina', grupo: null, cabeza_serie: false, ciudad: 'Medellín', delegado_nombre: 'Ana Ruiz', delegado_telefono: '3101234567',
  delegado_email: null, estado: 'pendiente_pago', valor: 150000, monto_pagado: 50000, saldo: 100000, motivo_retiro: null, origen: 'staff',
  pagos: [{ id: `p-${id}`, fecha: isoLocal(HOY), monto: 50000, anula_id: null, motivo: null, creado_en: '' }], ...extra,
});

describe('TorneosPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<TorneosPage>;

  async function cargar(permisos: string[], lista: Torneo[]) {
    TestBed.configureTestingModule({
      imports: [TorneosPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([]), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, tutorial_visto: true, tutoriales_vistos: [], permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(TorneosPage);
    fixture.detectChanges();
    backend.expectOne(`${API}/torneos`).flush(lista);
    await estable();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const texto = () => el().textContent ?? '';
  const ultimo = () => [...el().querySelectorAll('dialog')].at(-1)!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.replace(/\s+/g, ' ').trim().startsWith(t)) as HTMLButtonElement | undefined;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  function escribir(selector: string, valor: string) {
    const c = ultimo().querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    c.value = valor;
    c.dispatchEvent(new Event(c instanceof HTMLSelectElement ? 'change' : 'input'));
  }

  it('separa próximos, pasados y cancelados, con indicadores', async () => {
    await cargar(ADMIN, [
      torneo('1'),
      torneo('2', { fecha_inicio: isoLocal(sumarDias(HOY, -10)), fecha_fin: isoLocal(sumarDias(HOY, -9)) }),
      torneo('3', { estado: 'cancelado' }),
    ]);
    expect(el().querySelectorAll('.torneo').length).toBe(1);
    expect(el().querySelector('.kpis')!.textContent).toContain('$100.000'); // 2 cupos × 150.000 − 200.000 recaudado
    boton('Cancelados')!.click();
    await estable();
    expect(el().querySelector('.torneo h2')?.textContent).toContain('Copa 3');
  });

  it('crea un torneo: campos vacíos, cupo vacío = sugerido', async () => {
    await cargar(ADMIN, []);
    boton('add Nuevo torneo')!.click();
    await estable();
    expect(ultimo().querySelector<HTMLInputElement>('[formcontrolname="nombre"]')!.value).toBe('');
    escribir('[formcontrolname="nombre"]', 'Copa Dragones');
    escribir('[formcontrolname="rama"]', 'femenina');
    escribir('[formcontrolname="fecha"]', isoLocal(sumarDias(HOY, 30)));
    escribir('[formcontrolname="valor_inscripcion"]', '150000');
    await estable();
    boton('Crear torneo', ultimo())!.click();
    const r = backend.expectOne((x) => x.method === 'POST' && x.url === `${API}/torneos`);
    const dia = isoLocal(sumarDias(HOY, 30));
    expect(r.request.body).toMatchObject({
      nombre: 'Copa Dragones', lugar: null, valor_inscripcion: 150000, fecha_inicio: dia, fecha_fin: dia,
      fecha_limite_inscripcion: null, // sin fecha límite: el sitio inscribe hasta el día de inicio
      jornadas: [{ rama: 'femenina', fecha: dia, sedes: [] }],
    });
    expect(r.request.body.cupo_equipos).toBeUndefined();
    r.flush(torneo('9', { nombre: 'Copa Dragones' }));
    backend.expectOne(`${API}/torneos`).flush([torneo('9')]);
    await estable();
    expect(texto()).toContain('se cancelan solos');
  });

  it('en los clubes registra pagos y retira; anular solo el SuperAdmin', async () => {
    await cargar(ADMIN, [torneo('1')]);
    boton('groups Clubes')!.click();
    await estable();
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a'), equipo('b', { estado: 'en_espera', monto_pagado: 0, pagos: [] })]);
    await estable();
    expect(ultimo().querySelectorAll('.equipo').length).toBe(2);
    expect(ultimo().querySelector('a[href^="https://wa.me/573101234567"]')).not.toBeNull();
    expect(boton('Anular', ultimo())).toBeUndefined();

    boton('Registrar pago', ultimo())!.click();
    await estable();
    boton('Usar el saldo completo', ultimo())!.click();
    boton('Registrar', ultimo().querySelector('form')!)!.click();
    const pago = backend.expectOne(`${API}/torneos/1/equipos/a/pagos`);
    expect(pago.request.body).toEqual({ monto: 100000, fecha: isoLocal(HOY) });
    pago.flush(equipo('a', { estado: 'confirmado', monto_pagado: 150000, saldo: 0 }));
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a', { estado: 'confirmado', saldo: 0 })]);
    backend.expectOne(`${API}/torneos/1`).flush(torneo('1'));
    await estable();
    expect(texto()).toContain('queda confirmado');
  });

  it('el SuperAdmin anula un pago sin motivo y eliminar pide confirmación', async () => {
    await cargar(SUPERADMIN, [torneo('1')]);
    boton('groups Clubes')!.click();
    await estable();
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a')]);
    await estable();
    boton('Anular', ultimo())!.click();
    await estable();
    boton('Anular pago', ultimo())!.click();
    const r = backend.expectOne(`${API}/torneos/1/equipos/a/pagos/p-a/anular`);
    expect(r.request.body).toEqual({ motivo: null });
    r.flush(equipo('a', { monto_pagado: 0, saldo: 150000 }));
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a')]);
    backend.expectOne(`${API}/torneos/1`).flush(torneo('1'));
    await estable();
    expect(texto()).toContain('Pago anulado');
  });

  it('eliminar un torneo', async () => {
    await cargar(ADMIN, [torneo('1', { recaudado: 0 })]);
    el().querySelector<HTMLButtonElement>('[aria-label="Eliminar Copa 1"]')!.click();
    await estable();
    boton('Eliminar torneo', ultimo())!.click();
    backend.expectOne((x) => x.method === 'DELETE' && x.url === `${API}/torneos/1`).flush(null, { status: 204, statusText: 'No Content' });
    backend.expectOne(`${API}/torneos`).flush([]);
    await estable();
    expect(texto()).toContain('«Copa 1» eliminado');
  });

  it('sube el flyer del torneo al crearlo', async () => {
    globalThis.URL.createObjectURL ??= () => 'blob:prueba';
    globalThis.URL.revokeObjectURL ??= () => undefined;
    await cargar(ADMIN, []);
    boton('add Nuevo torneo')!.click();
    await estable();
    escribir('[formcontrolname="nombre"]', 'Copa Flyer');
    escribir('[formcontrolname="rama"]', 'femenina');
    escribir('[formcontrolname="fecha"]', isoLocal(sumarDias(HOY, 20)));
    escribir('[formcontrolname="fecha_limite_inscripcion"]', isoLocal(sumarDias(HOY, 10)));
    escribir('[formcontrolname="valor_inscripcion"]', '150000');
    const input = ultimo().querySelector<HTMLInputElement>('input[type="file"]')!;
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'flyer.jpg', { type: 'image/jpeg' })] });
    input.dispatchEvent(new Event('change'));
    boton('Crear torneo', ultimo())!.click();
    const crear = backend.expectOne(`${API}/torneos`);
    expect(crear.request.method).toBe('POST');
    crear.flush(torneo('9', { nombre: 'Copa Flyer' }));
    const flyer = backend.expectOne(`${API}/torneos/9/anuncio`);
    expect(flyer.request.method).toBe('POST');
    expect(flyer.request.body instanceof FormData).toBe(true);
    flyer.flush(torneo('9', { nombre: 'Copa Flyer', anuncio: 'abcd1234', anuncio_ancho: 1080, anuncio_alto: 1350 }));
    backend.expectOne(`${API}/torneos`).flush([torneo('9', { nombre: 'Copa Flyer', anuncio: 'abcd1234' })]);
    await estable();
    expect(texto()).toContain('«Copa Flyer» creado');
    expect(el().querySelector('.chip-anuncio')).not.toBeNull();
  });

  it('pasa un torneo ya jugado a torneos realizados (solo con permiso del sitio)', async () => {
    const jugado = torneo('5', { fecha_inicio: isoLocal(sumarDias(HOY, -3)), fecha_fin: isoLocal(sumarDias(HOY, -2)) });
    await cargar([...ADMIN, 'club.editar'], [jugado]);
    boton('Pasados')!.click();
    await estable();
    boton('history Pasar a realizados')!.click();
    const r = backend.expectOne(`${API}/torneos/5/realizado`);
    expect(r.request.method).toBe('POST');
    r.flush({ id: 'r1' });
    backend.expectOne(`${API}/torneos`).flush([{ ...jugado, realizado_id: 'r1' }]);
    await estable();
    expect(texto()).toContain('«Copa 5» pasó a Torneos realizados');
    expect(boton('history Pasar a realizados')).toBeUndefined();
    expect(el().querySelector('a.chip-realizado')?.getAttribute('href')).toBe('/perfil-club/torneos');
  });

  it('sin permiso del sitio no ofrece pasarlo a realizados', async () => {
    await cargar(ADMIN, [torneo('6', { fecha_inicio: isoLocal(HOY) })]);
    expect(boton('history Pasar a realizados')).toBeUndefined();
  });

  it('un torneo de fin de semana: dos jornadas con sus sedes; cada equipo muestra su rama y su grupo', async () => {
    const SAB = isoLocal(sumarDias(HOY, 20));
    const DOM = isoLocal(sumarDias(HOY, 21));
    const doble = torneo('7', {
      rama: null, jornadas: [
        { rama: 'femenina', fecha: SAB, sedes: ['Coliseo Mayor', 'Coliseo Sur'] },
        { rama: 'masculina', fecha: DOM, sedes: ['Coliseo Mayor', 'Coliseo Sur'] },
      ],
    });
    await cargar(ADMIN, [doble]);
    expect(texto()).toContain('Femenina y masculina');
    expect(texto()).toContain('Coliseo Mayor, Coliseo Sur');

    boton('groups Clubes')!.click();
    backend.expectOne(`${API}/torneos/7/equipos`).flush([equipo('a', { rama: 'masculina', grupo: 'B', cabeza_serie: true })]);
    await estable();
    const chips = ultimo().querySelector('.equipo-sede')!.textContent;
    expect(chips).toContain('masculina');
    expect(chips).toContain('Grupo B');
    expect(chips).toContain('Cabeza de serie');
    expect(ultimo().querySelector('select[aria-label^="Sede de"]')).toBeNull(); // la sede ya no es por equipo
  });

  it('el staff inscribe hasta el último día aunque el sitio ya cerró', async () => {
    const hoy = isoLocal(HOY);
    await cargar(ADMIN, [torneo('8', {
      fecha_inicio: hoy, fecha_fin: hoy, fecha_limite_inscripcion: null, inscripcion_hasta: isoLocal(sumarDias(HOY, -1)),
    })]);
    expect(texto()).toContain('sitio: inscripción cerrada');
    boton('groups Clubes')!.click();
    backend.expectOne(`${API}/torneos/8/equipos`).flush([]);
    await estable();
    expect(boton('add Inscribir club', ultimo())).toBeDefined();
  });

  it('sortea los grupos de una rama, los ajusta y los confirma', async () => {
    const sorteo = (extra: Partial<SorteoGrupos> = {}): SorteoGrupos => ({
      rama: 'femenina', sorteado_en: '2026-11-26T10:00:00-05:00', confirmado_en: null, sedes: ['Coliseo Mayor', 'Coliseo Sur'],
      grupos: [
        { id: 'gA', letra: 'A', sede: null, equipos: [{ id: 'a', nombre_club: 'Club a', ciudad: 'Medellín', estado: 'pendiente_pago', cabeza_serie: true }] },
        { id: 'gB', letra: 'B', sede: null, equipos: [{ id: 'b', nombre_club: 'Club b', ciudad: 'Bello', estado: 'confirmado', cabeza_serie: false }] },
      ],
      sin_grupo: [], actas: [], ...extra,
    });
    await cargar(ADMIN, [torneo('1', { jornadas: [{ rama: 'femenina', fecha: isoLocal(sumarDias(HOY, 20)), sedes: ['Coliseo Mayor', 'Coliseo Sur'] }] })]);
    boton('grid_view Grupos')!.click();
    await estable();
    const equipos = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'].map((id) => equipo(id));
    backend.expectOne(`${API}/torneos/1/grupos`).flush([]);
    backend.expectOne(`${API}/torneos/1/equipos`).flush(equipos);
    await estable();
    // 9 equipos: sugiere 3 grupos (3 de 3) y deja elegir entre 2 y 4.
    const cantidad = ultimo().querySelector<HTMLSelectElement>('select[aria-label="Cuántos grupos en la rama femenina"]')!;
    expect([...cantidad.options].map((o) => o.value)).toEqual(['2', '3', '4']);
    expect(cantidad.value).toBe('3');
    expect(texto()).toContain('3 de 3 equipos');

    // Marcar una cabeza de serie.
    ultimo().querySelector<HTMLButtonElement>('button[aria-label="Marcar cabeza de serie a Club a"]')!.click();
    const cabeza = backend.expectOne(`${API}/torneos/1/equipos/a/cabeza-serie`);
    expect(cabeza.request.body).toEqual({ cabeza_serie: true });
    cabeza.flush(equipo('a', { cabeza_serie: true }));
    backend.expectOne(`${API}/torneos/1/grupos`).flush([]);
    backend.expectOne(`${API}/torneos/1/equipos`).flush(equipos);
    await estable();

    cantidad.value = '2';
    cantidad.dispatchEvent(new Event('change'));
    await estable();
    boton('shuffle Sortear grupos', ultimo())!.click();
    const sortear = backend.expectOne(`${API}/torneos/1/grupos/femenina/sortear`);
    expect(sortear.request.body).toEqual({ grupos: 2 });
    sortear.flush(sorteo());
    await estable();
    expect(texto()).toContain('Borrador');
    expect(ultimo().querySelectorAll('.grupo').length).toBe(2);
    expect(ultimo().querySelector('.debe')).not.toBeNull(); // Club a aún debe

    // Los controles para ajustar aparecen con «Ajustar».
    expect(ultimo().querySelector('select[aria-label="Sede del grupo A"]')).toBeNull();
    boton('tune Ajustar', ultimo())!.click();
    await estable();

    // Sede del grupo A.
    const sede = ultimo().querySelector<HTMLSelectElement>('select[aria-label="Sede del grupo A"]')!;
    sede.value = 'Coliseo Sur';
    sede.dispatchEvent(new Event('change'));
    const rs = backend.expectOne(`${API}/torneos/1/grupos/gA/sede`);
    expect(rs.request.body).toEqual({ sede: 'Coliseo Sur' });
    rs.flush(sorteo());
    await estable();

    // Mover a Club b al grupo A.
    const mover = ultimo().querySelector<HTMLSelectElement>('select[aria-label="Grupo de Club b"]')!;
    mover.value = 'gA';
    mover.dispatchEvent(new Event('change'));
    const rm = backend.expectOne(`${API}/torneos/1/equipos/b/grupo`);
    expect(rm.request.body).toEqual({ grupo_id: 'gA' });
    rm.flush(equipo('b', { grupo: 'A' }));
    backend.expectOne(`${API}/torneos/1/grupos`).flush([sorteo()]);
    backend.expectOne(`${API}/torneos/1/equipos`).flush(equipos);
    await estable();
    expect(texto()).toContain('Club b pasó al grupo A');

    // Confirmar y publicar.
    boton('verified Confirmar y publicar', ultimo())!.click();
    const rc = backend.expectOne(`${API}/torneos/1/grupos/femenina/confirmar`);
    expect(rc.request.method).toBe('POST');
    const acta = { orden: 1, huella: 'f'.repeat(64), creado_en: '2026-11-26T10:05:00-05:00', grupos: [
      { letra: 'A' as const, sede: 'Coliseo Sur', equipos: [{ club: 'Club a', ciudad: 'Medellín', cabeza_serie: true, estado: 'pendiente_pago' as const }] },
    ] };
    rc.flush(sorteo({ confirmado_en: '2026-11-26T10:05:00-05:00', actas: [acta] }));
    await estable();
    expect(texto()).toContain('Publicado');
    expect(texto()).toContain('acta n.º 1');
    expect(texto()).toContain('Club a*');

    // Volver a sortear algo ya publicado pide confirmación.
    boton('shuffle Volver a sortear', ultimo())!.click();
    await estable();
    expect(texto()).toContain('dejan de verse en el sitio');
    boton('Sí, volver a sortear', ultimo())!.click();
    backend.expectOne(`${API}/torneos/1/grupos/femenina/sortear`).flush(sorteo());
    await estable();
    expect(texto()).toContain('Borrador');
  });

  it('con menos de 4 equipos con cupo no ofrece sortear', async () => {
    await cargar(ADMIN, [torneo('1')]);
    boton('grid_view Grupos')!.click();
    await estable();
    backend.expectOne(`${API}/torneos/1/grupos`).flush([]);
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a'), equipo('b'), equipo('c'), equipo('d', { estado: 'en_espera' })]);
    await estable();
    expect(texto()).toContain('al menos 4 equipos con cupo');
    expect(boton('shuffle Sortear grupos', ultimo())).toBeUndefined();
  });
});

describe('gruposSugeridos', () => {
  it('de a 4 más o menos, entre 2 y 8, con al menos dos por grupo', () => {
    expect([4, 5, 8, 9, 12, 18, 40, 100].map(gruposSugeridos)).toEqual([2, 2, 2, 3, 3, 5, 8, 8]);
  });
});
