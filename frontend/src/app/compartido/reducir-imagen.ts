/** Por debajo de este peso la foto se sube tal cual (el servidor la vuelve a codificar de todos modos). */
const PESO_SIN_REDUCIR = 2 * 1024 * 1024;

/**
 * Reduce una foto en el navegador antes de subirla: lado mayor `maxLado` px, JPEG.
 *
 * Las fotos de cámara (20–60 MB, 24–60 Mpx) superan el máximo del servidor; reducidas pesan ~1–2 MB, suben
 * mucho más rápido y conservan más resolución de la que el servidor guarda (1920 px). El lienzo no copia los
 * metadatos (EXIF/ubicación). Si el navegador no puede leerla, se devuelve el original y decide el servidor.
 */
export async function reducirImagen(archivo: File, maxLado = 2560, calidad = 0.9): Promise<File> {
  if (archivo.size <= PESO_SIN_REDUCIR || typeof createImageBitmap !== 'function') return archivo;
  try {
    const imagen = await createImageBitmap(archivo, { imageOrientation: 'from-image' });
    const escala = Math.min(1, maxLado / Math.max(imagen.width, imagen.height));
    const lienzo = document.createElement('canvas');
    lienzo.width = Math.round(imagen.width * escala);
    lienzo.height = Math.round(imagen.height * escala);
    const ctx = lienzo.getContext('2d');
    if (!ctx) return archivo;
    ctx.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
    imagen.close();
    const blob = await new Promise<Blob | null>((ok) => lienzo.toBlob(ok, 'image/jpeg', calidad));
    if (!blob || blob.size >= archivo.size) return archivo;
    return new File([blob], archivo.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' });
  } catch {
    return archivo;
  }
}
