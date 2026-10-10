# Imágenes para la cámara simulada

`scripts/e2e/make_fake_video.py` convierte las imágenes de `faces/` en el
video `generated/camera.y4m`. Chromium lo usa como cámara en las pruebas e2e.
Ni las imágenes ni el video se suben al repositorio: `.gitignore` los excluye.

## Qué imagen usar

- Una o dos fotografías de un rostro **de frente**, con la cara completa,
  buena luz y sin gafas de sol ni mascarilla.
- Expresión clara y mantenida (por ejemplo, una sonrisa amplia): el analizador
  necesita la misma lectura durante al menos un segundo.
- Formato PNG o JPG. El script las encaja en 320 × 240 sin deformarlas.
- Mejor sin otras personas ni texto de fondo.

## De dónde sacarla

- **Solo imágenes propias** (por ejemplo, tu autorretrato) **o con una
  licencia que permita este uso** (dominio público o CC0, como un retrato
  generado o de un banco con licencia libre). Guarda la referencia de la
  licencia fuera del repositorio.
- **Nunca** fotografías de voluntarios, estudiantes ni personal de la
  UNHEVAL, ni imágenes tomadas de redes sociales.
- El repositorio no incluye fotos de personas reales.

## Generar el video

```powershell
# Desde la raíz del repositorio
python scripts/e2e/make_fake_video.py              # rostro + tramo sin persona
python scripts/e2e/make_fake_video.py --empty-only # solo sin persona
```

Sin imágenes en `faces/`, el script genera solo el tramo sin persona y las
pruebas que necesitan un rostro se marcan como omitidas.
