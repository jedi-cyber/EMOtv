# Guía de despliegue del consentimiento (administración)

Esta guía es para el equipo que despliega EMOtv. **No sustituye el documento
que el estudiante lee y acepta**. El texto provisional para demostración está
en `docs/consent-demo.md`; no cuenta como aprobación universitaria.

## Modos

| `CONSENT_MODE` | Uso | Regla para iniciar análisis |
| --- | --- | --- |
| `development` | Pruebas técnicas sin participantes reales | No exige aceptación |
| `demo` | Demostración informada | Política demo activa y aceptación vigente |
| `production` | Solo tras aprobación institucional | Política no demo, aprobada y vigente; aceptación de esa versión |

Si `ENVIRONMENT=production`, EMOtv rechaza `CONSENT_MODE=development` o `demo`.
El valor local por defecto es `demo`. El modo `development` jamás debe usarse
con estudiantes o participantes reales.

## Preparación y transición

1. Ejecute `python -m alembic upgrade head` con la base correcta. La migración
   `20260918_07` crea el catálogo persistente de políticas.
2. En demo, al iniciar FastAPI se registra y activa automáticamente la versión
   `EMOTV-CONSENT-DEMO-001:v0.1` si no hay otra activa. La pantalla `/consent`
   muestra su texto completo y la etiqueta de demostración.
3. Cuando exista aprobación institucional, un administrador carga mediante
   `POST /consent-policies` un documento nuevo con `code`, `version`, `title`,
   `content`, `effective_at` con zona horaria y `approved=true`. El ID será
   `code:version`. No sobrescriba una versión publicada: cree otra.
4. Revise `GET /consent-policies` y active con
   `POST /consent-policies/{id}/activate`. La anterior queda histórica y sus
   aceptaciones no habilitan nuevos análisis. El estudiante ve la nueva versión
   y debe aceptarla. Se conserva el historial de aceptaciones y revocaciones.
5. Configure `ENVIRONMENT=production` y `CONSENT_MODE=production` solo cuando
   estén completos la aprobación, la migración y los controles institucionales.
   Una política demo o sin aprobación no puede activarse en ese modo.

La revisión jurídica, la identificación del responsable, los plazos definitivos
y los canales para ejercer derechos siguen pendientes según
`docs/privacy-data-governance.md`. Marcar `approved=true` en la API debe
representar una aprobación real documentada, no una decisión técnica.
